from typing import Optional

from nonebot_plugin_orm import async_scoped_session
from sqlalchemy import delete, desc, func, select

from .config import config
from .models import ChatHistory


def format_context(history: list[dict], limit: Optional[int] = None) -> str:
    """把历史记录格式化成提示词上下文：「[昵称]: 内容」。

    - limit 只取最近 N 条；
    - 无历史时返回 "(无历史)"，供秘书决策与「天使之笑」共用。
    """
    records = history[-limit:] if limit else history

    lines: list[str] = []
    for msg in records:
        role = msg.get("role")
        name = msg.get("user_name") or (
            config.ai_chat_assistant_name if role == "assistant" else "用户"
        )
        lines.append(f"[{name}]: {msg.get('content', '')}")

    return "\n".join(lines) if lines else "(无历史)"


async def get_history(
    session: async_scoped_session,
    session_type: str,
    group_id: Optional[str],
    user_id: str,
) -> list[dict[str, str]]:
    """获取指定会话的最近 N 轮对话，按时间正序返回。"""
    stmt = (
        select(ChatHistory)
        .where(
            ChatHistory.session_type == session_type,
            ChatHistory.group_id.is_(None)
            if group_id is None
            else ChatHistory.group_id == group_id,
            ChatHistory.user_id == user_id,
        )
        # id 作为次级排序键，保证同一时间戳下的顺序稳定
        .order_by(desc(ChatHistory.created_at), desc(ChatHistory.id))
        .limit(config.ai_chat_max_history * 2)  # 每轮含 user + assistant
    )

    result = await session.execute(stmt)
    records = result.scalars().all()

    records.reverse()  # 反转为正序（从旧到新）
    return [
        {"role": r.role, "content": r.content, "user_name": r.user_name}
        for r in records
    ]


async def append_message(
    session: async_scoped_session,
    session_type: str,
    group_id: Optional[str],
    user_id: str,
    role: str,
    content: str,
    user_name: Optional[str] = None,
) -> None:
    """追加一条对话记录。"""
    record = ChatHistory(
        session_type=session_type,
        group_id=group_id,
        user_id=user_id,
        role=role,
        content=content,
        user_name=user_name,
    )
    session.add(record)
    await session.commit()


async def clear_history(
    session: async_scoped_session,
    session_type: str,
    group_id: Optional[str],
    user_id: str,
) -> int:
    """清空指定会话的对话历史，返回删除行数。"""
    stmt = delete(ChatHistory).where(
        ChatHistory.session_type == session_type,
        ChatHistory.group_id.is_(None)
        if group_id is None
        else ChatHistory.group_id == group_id,
        ChatHistory.user_id == user_id,
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0


async def count_group_messages(
    session: async_scoped_session,
    group_id: str,
) -> int:
    """统计某群的总消息数（可选，用于监控）。"""
    stmt = select(func.count(ChatHistory.id)).where(
        ChatHistory.session_type == "group",
        ChatHistory.group_id == group_id,
    )
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_group_speakers(
    session: async_scoped_session,
    group_id: str,
    limit: int = 10,
) -> list[dict]:
    """按 user_id 分组统计 user 消息数，降序返回前 limit 名。"""
    stmt = (
        select(
            ChatHistory.user_id,
            ChatHistory.user_name,
            func.count(ChatHistory.id).label("count"),
        )
        .where(
            ChatHistory.session_type == "group",
            ChatHistory.group_id == group_id,
            ChatHistory.role == "user",
        )
        .group_by(ChatHistory.user_id, ChatHistory.user_name)
        .order_by(desc(func.count(ChatHistory.id)))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return [
        {"user_id": row.user_id, "user_name": row.user_name, "count": row.count}
        for row in result.all()
    ]
