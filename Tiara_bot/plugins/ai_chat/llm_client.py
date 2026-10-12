"""DeepSeek（LangChain）客户端封装。

所有 langchain 相关导入都收敛在本模块，好处是：
- 依赖缺失（未执行 `uv sync`）或未配置 API Key 时抛出 `LLMUnavailableError`，
  由上层转换成对用户友好的提示，插件本身仍能正常加载；
- 客户端延迟创建并缓存，避免模块导入阶段就读配置、建连接。
"""

import logging
from typing import Any, Optional

from .config import config

logger = logging.getLogger("ai_chat.llm")


class LLMUnavailableError(RuntimeError):
    """LLM 依赖缺失或未配置 API Key。"""


_LC: Optional[tuple[Any, Any, Any, Any]] = None
_llm: Optional[Any] = None
_smile_llm: Optional[Any] = None


def _langchain() -> tuple[Any, Any, Any, Any]:
    """延迟导入 langchain，返回 (AIMessage, HumanMessage, SystemMessage, ChatDeepSeek)。"""
    global _LC
    if _LC is None:
        try:
            from langchain_core.messages import (
                AIMessage,
                HumanMessage,
                SystemMessage,
            )
            from langchain_deepseek import ChatDeepSeek
        except ImportError as e:  # pragma: no cover - 取决于运行环境
            raise LLMUnavailableError(
                "缺少依赖 langchain-deepseek，请先执行 uv sync"
            ) from e
        _LC = (AIMessage, HumanMessage, SystemMessage, ChatDeepSeek)
    return _LC


def build_llm(
    *,
    temperature: float,
    max_tokens: int,
    timeout: int,
    max_retries: int = 2,
) -> Any:
    """按给定参数构造 ChatDeepSeek 实例。"""
    if not config.deepseek_api_key:
        raise LLMUnavailableError("未配置 DEEPSEEK_API_KEY")
    *_, chat_deepseek = _langchain()
    return chat_deepseek(
        model=config.deepseek_model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        api_key=config.deepseek_api_key,
        max_retries=max_retries,
    )


def is_available() -> bool:
    """依赖与 API Key 是否就绪（不发起任何网络请求）。"""
    if not config.deepseek_api_key:
        return False
    try:
        _langchain()
    except LLMUnavailableError:
        return False
    return True


def get_llm() -> Any:
    """返回全局 LLM 单例（首次调用时创建）。"""
    global _llm
    if _llm is None:
        _llm = build_llm(
            temperature=config.deepseek_temperature,
            max_tokens=config.deepseek_max_tokens,
            timeout=config.deepseek_timeout,
            max_retries=2,
        )
        logger.info("DeepSeek 客户端已就绪：model=%s", config.deepseek_model)
    return _llm


def get_smile_llm() -> Any:
    """「天使之笑」专用客户端：高温度、极短回复，复用单例避免每次重建。"""
    global _smile_llm
    if _smile_llm is None:
        _smile_llm = build_llm(
            temperature=0.9,
            max_tokens=config.angel_smile_max_tokens,
            timeout=10,
            max_retries=1,
        )
    return _smile_llm


def content_to_str(content: Any) -> str:
    """将 LLM 返回的 content 统一为 str。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


async def ainvoke(llm: Any, system_prompt: str, user_prompt: str) -> str:
    """单轮（system + user）异步调用，供秘书决策等轻量场景使用。"""
    _, human_message, system_message, _ = _langchain()
    response = await llm.ainvoke(
        [
            system_message(content=system_prompt),
            human_message(content=user_prompt),
        ]
    )
    return content_to_str(response.content)


async def chat_with_history(
    system_prompt: str,
    history: list[dict[str, str]],
    user_input: str,
) -> str:
    """携带历史记录异步调用 DeepSeek。

    history 格式：[{"role": "user"/"assistant", "content": "..."}]
    """
    ai_message, human_message, system_message, _ = _langchain()

    messages: list[Any] = [system_message(content=system_prompt)]

    for msg in history:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            messages.append(human_message(content=content))
        elif role == "assistant":
            messages.append(ai_message(content=content))

    messages.append(human_message(content=user_input))

    logger.debug("Calling DeepSeek with %d messages", len(messages))

    response = await get_llm().ainvoke(messages)
    return content_to_str(response.content)


async def chat_angel_smile(context: str, latest_message: str) -> str:
    """低能量时的「天使之笑」：一句极简回应。"""
    _, human_message, system_message, _ = _langchain()
    response = await get_smile_llm().ainvoke(
        [
            system_message(content=config.angel_smile_prompt),
            human_message(
                content=(
                    f"群聊记录：\n{context}\n\n"
                    f"最新消息：{latest_message}\n\n请简短回应。"
                )
            ),
        ]
    )
    return content_to_str(response.content)
