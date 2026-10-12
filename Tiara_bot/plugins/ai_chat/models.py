from datetime import datetime
from typing import Optional

from nonebot import require

require("nonebot_plugin_orm")
from nonebot_plugin_orm import Model
from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class ChatHistory(Model):
    """AI 对话历史表"""

    __tablename__ = "ai_chat_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 会话类型：private / group
    session_type: Mapped[str] = mapped_column(String(16), index=True)
    # 群号，私聊为 None
    group_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    # 发言人 QQ 号
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    # 发言人昵称
    user_name: Mapped[Optional[str]] = mapped_column(String(128), default=None)
    # 角色：user / assistant
    role: Mapped[str] = mapped_column(String(16))
    # 消息内容
    content: Mapped[str] = mapped_column(Text)
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    __table_args__ = (
        Index(
            "ix_ai_chat_lookup",
            "session_type",
            "group_id",
            "user_id",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ChatHistory id={self.id} session={self.session_type} "
            f"group={self.group_id} user={self.user_id}({self.user_name}) "
            f"role={self.role}>"
        )


class ChatEnergy(Model):
    """AI 聊天能量表"""

    __tablename__ = "ai_chat_energy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 群号（私聊用 private:{user_id}）
    group_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # 当前能量（0.0 ~ 1.0）
    energy: Mapped[float] = mapped_column(Float, default=1.0)
    # 上次能量恢复时间戳
    last_recovery: Mapped[int] = mapped_column(Integer, default=0)
    # 上次主动回复时间戳
    last_proactive_reply: Mapped[int] = mapped_column(Integer, default=0)
    # 状态机字段：not_present / summoned / getting_familiar / observation
    bot_state: Mapped[str] = mapped_column(String(32), default="not_present")
    # 更新时间
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    def __repr__(self) -> str:
        return (
            f"<ChatEnergy group={self.group_id} energy={self.energy:.2f} "
            f"state={self.bot_state}>"
        )
