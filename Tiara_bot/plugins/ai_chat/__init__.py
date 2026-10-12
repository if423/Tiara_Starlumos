"""AI 聊天插件入口。

回复策略：
- 被 @ / 私聊：必定回复，跳过概率与秘书决策；
- 群聊中未被 @：概率预筛 → 秘书决策 → 能量检查 → 主动插话；
- 「天使之笑」：能量偏低时只回一句极简的话。

指令：/聊、/重置对话、/人格列表、/切换人格、/重载人格。
"""

import logging
import random
from typing import Any, Optional

from nonebot import on_command, on_message, require
from nonebot.adapters import Bot, Event, Message
from nonebot.adapters.satori.models import ChannelType
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from nonebot.rule import Rule

require("nonebot_plugin_orm")
from nonebot_plugin_orm import async_scoped_session

from .config import AIChatConfig, config
from .energy import (
    can_proactive_reply,
    consume_energy,
    mark_proactive_reply,
    recover_energy,
    update_bot_state,
)
from .llm_client import LLMUnavailableError, chat_angel_smile, chat_with_history
from .memory import append_message, clear_history, format_context, get_history
from .persona_loader import (
    get_default_persona_name,
    list_personas,
    load_persona,
    reload_personas,
    set_default_persona,
)
from .secretary import secretary_decide

__plugin_meta__ = PluginMetadata(
    name="ai_chat",
    description="AI 聊天插件：对话记忆、人格加载、主动回复、能量系统",
    usage=(
        "被 @ 时必定回复；发送「/聊 <内容>」强制对话；"
        "「/重置对话」清空历史；「/人格列表」「/切换人格」「/重载人格」管理人格"
    ),
    type="application",
    config=AIChatConfig,
    extra={},
)

logger = logging.getLogger("ai_chat")

_FALLBACK_SYSTEM_PROMPT = "你是一个友好的 QQ 助手。"

# 主动回复时按秘书建议的长度追加的提示词
_STRATEGY_HINTS = {
    "short": "请简短回复，1-2 句话即可。",
    "medium": "请正常回复，3-5 句话。",
    "long": "请详细回复，可以展开说明。",
}


async def _is_enabled() -> bool:
    """插件总开关，供 Rule 使用（AI_CHAT_ENABLED=false 时全部静默）。"""
    return config.ai_chat_enabled


# ============================================================
# 会话标识工具
# ============================================================

def _extract_session_info(event: Event) -> tuple[str, Optional[str], str]:
    """从事件中提取会话信息，返回 (session_type, group_id, user_id)。

    - 群聊：("group", 群号, user_id)
    - 私聊：("private", None, user_id)
    """
    user_id = event.get_user_id()

    channel = getattr(event, "channel", None)

    # Satori 的私聊频道类型为 DIRECT，这类事件不能当作群聊处理
    if getattr(channel, "type", None) == ChannelType.DIRECT:
        return "private", None, user_id

    # 群聊事件带 guild 属性
    guild = getattr(event, "guild", None)
    if guild is not None:
        return "group", str(guild.id), user_id

    # 兼容只有 channel、没有 guild 的适配器
    if channel is not None:
        return "group", str(channel.id), user_id

    return "private", None, user_id


def _extract_user_name(event: Event) -> Optional[str]:
    """按优先级提取昵称：群昵称 > 用户昵称 > 用户名 > 其它适配器的 sender。"""
    member = getattr(event, "member", None)
    if member is not None and getattr(member, "nick", None):
        return member.nick

    user = getattr(event, "user", None)
    if user is not None:
        if getattr(user, "nick", None):
            return user.nick
        if getattr(user, "name", None):
            return user.name

    sender = getattr(event, "sender", None)
    if sender is not None:
        for attr in ("nickname", "card", "name"):
            value = getattr(sender, attr, None)
            if value:
                return value

    return None


def _is_to_me(event: Event) -> bool:
    """是否在叫机器人（Satori 由平台标记 to_me，私聊事件恒为 True）。"""
    is_tome = getattr(event, "is_tome", None)
    if not callable(is_tome):
        return False
    try:
        return bool(is_tome())
    except Exception:  # pragma: no cover - 适配器实现差异
        return False


def _is_from_self(bot: Bot, event: Event) -> bool:
    """忽略机器人自己发出的消息，避免自问自答。"""
    user = getattr(event, "user", None)
    if user is None:
        return False
    return str(getattr(user, "id", "")) == str(bot.self_id)


# ============================================================
# 内部生成函数
# ============================================================

def _build_system_prompt(
    is_proactive: bool = False,
    strategy: str = "medium",
) -> str:
    """加载当前人格，并按需追加回复长度提示。"""
    persona = load_persona(get_default_persona_name())
    system_prompt = persona.prompt if persona else _FALLBACK_SYSTEM_PROMPT

    if is_proactive:
        hint = _STRATEGY_HINTS.get(strategy, _STRATEGY_HINTS["medium"])
        system_prompt = f"{system_prompt}\n{hint}"

    return system_prompt


async def _save_reply(
    session: async_scoped_session,
    session_type: str,
    group_id: Optional[str],
    user_id: str,
    reply: str,
) -> None:
    """把机器人的回复写入对话历史。"""
    await append_message(
        session,
        session_type,
        group_id,
        user_id,
        role="assistant",
        content=reply,
        user_name=config.ai_chat_assistant_name,
    )


async def _generate_and_reply(
    matcher: Any,
    session: async_scoped_session,
    session_type: str,
    group_id: Optional[str],
    user_id: str,
    history: list[dict],
    user_input: str,
    is_proactive: bool = False,
    strategy: str = "medium",
) -> bool:
    """加载人格、调用 LLM、保存并发送回复；返回是否真的产生了回复。"""
    system_prompt = _build_system_prompt(is_proactive, strategy)

    try:
        reply = await chat_with_history(system_prompt, history, user_input)
    except LLMUnavailableError as e:
        logger.warning("AI 服务不可用：%s", e)
        if not is_proactive:
            await matcher.finish(f"AI 服务暂时不可用。（{e}）")
        return False
    except Exception as e:
        logger.exception("DeepSeek 调用失败")
        if not is_proactive:
            await matcher.finish(f"AI 服务暂时不可用。({type(e).__name__})")
        return False

    reply = reply.strip()
    if not reply:
        return False

    await _save_reply(session, session_type, group_id, user_id, reply)

    if is_proactive and group_id:
        await consume_energy(session, group_id, len(reply))

    await matcher.send(reply)
    return True


async def _generate_angel_smile(
    matcher: Any,
    session: async_scoped_session,
    session_type: str,
    group_id: Optional[str],
    user_id: str,
    history: list[dict],
    user_input: str,
) -> bool:
    """低能量时的「天使之笑」：一句极简回应，同样计入冷却与能量消耗。"""
    context = format_context(history, 3)

    try:
        reply = await chat_angel_smile(context, user_input)
    except LLMUnavailableError as e:
        logger.warning("天使之笑不可用：%s", e)
        return False
    except Exception as e:
        logger.warning("Angel smile failed: %s", e)
        return False

    reply = reply.strip()
    if not reply:
        return False

    await _save_reply(session, session_type, group_id, user_id, reply)

    if group_id:
        await consume_energy(session, group_id, len(reply))
        await mark_proactive_reply(session, group_id)

    await matcher.send(reply)
    return True


# ============================================================
# Matcher 1：消息监听（@ 必定回复，非 @ 走主动回复决策）
# ============================================================

ai_chat_matcher = on_message(
    rule=Rule(_is_enabled),
    priority=config.ai_chat_priority,
    block=False,
)


@ai_chat_matcher.handle()
async def handle_ai_chat(
    bot: Bot,
    event: Event,
    session: async_scoped_session,
) -> None:
    if _is_from_self(bot, event):
        return

    user_input = event.get_plaintext().strip()
    if not user_input:
        return

    session_type, group_id, user_id = _extract_session_info(event)
    user_name = _extract_user_name(event)
    is_at_me = _is_to_me(event)

    # 先取历史再写库：当前这条消息由 chat_with_history / secretary_decide
    # 单独传入，避免在上下文里重复出现
    try:
        history = await get_history(session, session_type, group_id, user_id)
        await append_message(
            session,
            session_type,
            group_id,
            user_id,
            role="user",
            content=user_input,
            user_name=user_name,
        )
    except Exception as e:
        logger.exception("对话历史读写失败：%s", e)
        return

    # 分支 A：被 @ 必定回复，跳过概率与决策
    if is_at_me:
        replied = await _generate_and_reply(
            ai_chat_matcher,
            session,
            session_type,
            group_id,
            user_id,
            history,
            user_input,
            is_proactive=False,
        )
        if replied and group_id:
            try:
                await update_bot_state(session, group_id, "summoned")
            except Exception as e:  # 状态字段仅用于观测，失败不影响回复
                logger.warning("更新 bot_state 失败：%s", e)
        return

    # 分支 B：非 @ 的主动回复
    if session_type != "group" or not group_id:
        return
    if not config.ai_chat_proactive_enabled:
        return
    if len(user_input) < 2:
        return
    if random.random() > config.proactive_base_prob:
        return
    if not await can_proactive_reply(session, group_id):
        return

    decision = await secretary_decide(history, user_input)
    if decision is None or not decision["should_reply"]:
        return
    if decision["confidence"] < config.secretary_reply_threshold:
        return

    energy = await recover_energy(session, group_id)
    if energy < config.energy_threshold_smile:
        return
    if energy < config.energy_threshold_reply:
        await _generate_angel_smile(
            ai_chat_matcher,
            session,
            session_type,
            group_id,
            user_id,
            history,
            user_input,
        )
        return

    replied = await _generate_and_reply(
        ai_chat_matcher,
        session,
        session_type,
        group_id,
        user_id,
        history,
        user_input,
        is_proactive=True,
        strategy=decision["strategy"],
    )
    if replied:
        await mark_proactive_reply(session, group_id)


# ============================================================
# Matcher 2：/聊 命令（不依赖 @）
# ============================================================

chat_cmd = on_command(
    "聊",
    rule=Rule(_is_enabled),
    priority=config.ai_chat_priority,
    block=True,
)


@chat_cmd.handle()
async def handle_chat_cmd(
    event: Event,
    session: async_scoped_session,
    args: Message = CommandArg(),
) -> None:
    user_input = args.extract_plain_text().strip()
    if not user_input:
        await chat_cmd.finish("请在指令后附上内容，例如：/聊 你好")

    session_type, group_id, user_id = _extract_session_info(event)
    user_name = _extract_user_name(event)

    try:
        history = await get_history(session, session_type, group_id, user_id)
        await append_message(
            session,
            session_type,
            group_id,
            user_id,
            role="user",
            content=user_input,
            user_name=user_name,
        )
    except Exception as e:
        logger.exception("对话历史读写失败：%s", e)
        await chat_cmd.finish("对话记录暂时不可用，请稍后再试。")

    try:
        reply = await chat_with_history(
            _build_system_prompt(),
            history,
            user_input,
        )
    except LLMUnavailableError as e:
        logger.warning("AI 服务不可用：%s", e)
        await chat_cmd.finish(f"AI 服务暂时不可用。（{e}）")
    except Exception as e:
        logger.exception("DeepSeek 调用失败")
        await chat_cmd.finish(f"AI 服务暂时不可用。({type(e).__name__})")

    reply = reply.strip()
    if not reply:
        await chat_cmd.finish("AI 暂时没有想出回复，请稍后再试。")

    await _save_reply(session, session_type, group_id, user_id, reply)
    await chat_cmd.finish(reply)


# ============================================================
# Matcher 3：/重置对话
# ============================================================

reset_cmd = on_command(
    "重置对话",
    rule=Rule(_is_enabled),
    priority=10,
    block=True,
)


@reset_cmd.handle()
async def handle_reset(
    event: Event,
    session: async_scoped_session,
) -> None:
    session_type, group_id, user_id = _extract_session_info(event)
    deleted = await clear_history(session, session_type, group_id, user_id)

    if deleted > 0:
        await reset_cmd.finish(f"已清空你的对话历史（{deleted} 条）。")
    await reset_cmd.finish("你没有对话历史。")


# ============================================================
# Matcher 4：/人格列表
# ============================================================

persona_list_cmd = on_command(
    "人格列表",
    rule=Rule(_is_enabled),
    priority=10,
    block=True,
)


@persona_list_cmd.handle()
async def handle_persona_list() -> None:
    personas = list_personas()
    if not personas:
        await persona_list_cmd.finish("当前没有可用人格。")

    current = get_default_persona_name()
    lines = [f"当前人格：{current}", "可用人格："]
    for p in personas:
        marker = " ← 当前" if p.name == current else ""
        lines.append(f"  · {p.name} — {p.description}{marker}")

    await persona_list_cmd.finish("\n".join(lines))


# ============================================================
# Matcher 5：/切换人格（仅 SUPERUSER）
# ============================================================

persona_switch_cmd = on_command(
    "切换人格",
    rule=Rule(_is_enabled),
    priority=10,
    block=True,
    permission=SUPERUSER,
)


@persona_switch_cmd.handle()
async def handle_persona_switch(args: Message = CommandArg()) -> None:
    name = args.extract_plain_text().strip()
    if not name:
        await persona_switch_cmd.finish("用法：/切换人格 <人格名>")

    if not set_default_persona(name):
        await persona_switch_cmd.finish(f"人格「{name}」不存在。")

    persona = load_persona(name)
    description = persona.description if persona else ""
    await persona_switch_cmd.finish(
        f"已切换为「{name}」：{description}（已保存，重启后仍然生效）"
    )


# ============================================================
# Matcher 6：/重载人格（热重载，仅 SUPERUSER）
# ============================================================

reload_persona_cmd = on_command(
    "重载人格",
    rule=Rule(_is_enabled),
    priority=10,
    block=True,
    permission=SUPERUSER,
)


@reload_persona_cmd.handle()
async def handle_reload_persona() -> None:
    count = reload_personas()
    await reload_persona_cmd.finish(f"已重新加载 {count} 个人格。")
