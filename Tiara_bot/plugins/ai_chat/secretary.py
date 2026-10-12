import json
import logging
import re
from typing import Any, Optional

from .config import config
from .llm_client import LLMUnavailableError, ainvoke, build_llm
from .memory import format_context

logger = logging.getLogger("ai_chat.secretary")

SECRETARY_SYSTEM_PROMPT = """你是一个群聊参与决策助手。你的任务是根据最近的群聊记录，判断机器人是否应该主动参与对话。

请以 JSON 格式输出，不要输出任何其他内容：
{
  "should_reply": true/false,
  "reason": "简短理由（不超过20字）",
  "strategy": "short/medium/long",
  "confidence": 0.0~1.0
}

判断标准：
- 如果消息是在向机器人提问、提到了机器人、或话题明显需要机器人参与 → should_reply=true
- 如果是用户之间的闲聊，机器人没有合适的切入点 → should_reply=false
- 如果群聊正在激烈讨论且机器人插话会打断 → should_reply=false
- 如果消息是表情、无意义内容、或机器人刚回复过 → should_reply=false
- strategy 表示建议的回复长度：short(1-2句)、medium(3-5句)、long(展开说明)"""

_VALID_STRATEGIES = ("short", "medium", "long")

_secretary_llm: Optional[Any] = None


def _get_secretary_llm() -> Any:
    """秘书专用客户端：低温度 + 极短输出，复用单例。"""
    global _secretary_llm
    if _secretary_llm is None:
        _secretary_llm = build_llm(
            temperature=0.3,
            max_tokens=config.secretary_max_tokens,
            timeout=10,
            max_retries=1,
        )
    return _secretary_llm


def _to_confidence(value: Any) -> float:
    """把模型返回的置信度安全地归一到 [0, 1]。"""
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, confidence))


async def secretary_decide(
    history: list[dict],
    latest_message: str,
) -> Optional[dict]:
    """秘书决策：判断机器人是否值得主动回复。任何异常返回 None。"""
    context_text = format_context(history, 5)

    user_prompt = (
        f"最近的群聊记录：\n{context_text}\n\n"
        f"最新消息：{latest_message}\n\n"
        f"请判断机器人是否应该主动参与这次对话。"
    )

    try:
        content = await ainvoke(
            _get_secretary_llm(),
            SECRETARY_SYSTEM_PROMPT,
            user_prompt,
        )
    except LLMUnavailableError as e:
        logger.warning("秘书决策不可用：%s", e)
        return None
    except Exception as e:
        logger.warning("Secretary decide failed: %s", e)
        return None

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        logger.warning("Secretary returned non-JSON: %r", content)
        return None

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        logger.warning("Secretary JSON parse failed: %r", content)
        return None

    if not isinstance(data, dict):
        logger.warning("Secretary returned non-object JSON: %r", content)
        return None

    strategy = str(data.get("strategy", "medium")).strip().lower()
    if strategy not in _VALID_STRATEGIES:
        strategy = "medium"

    return {
        "should_reply": bool(data.get("should_reply", False)),
        "reason": str(data.get("reason", "")),
        "strategy": strategy,
        "confidence": _to_confidence(data.get("confidence", 0.0)),
    }
