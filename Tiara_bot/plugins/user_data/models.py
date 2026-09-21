from datetime import datetime
from typing import Optional

from nonebot_plugin_orm import Model
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


class User(Model):
    """用户基本信息表"""

    __tablename__ = "bot_user"

    # 内部主键，自增
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # QQ号（核心标识），必须使用 BigInteger，且唯一、建立索引
    user_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, comment="QQ号"
    )
    # 基础信息
    nickname: Mapped[str] = mapped_column(
        String(128), default="未知用户", comment="最后记录的昵称"
    )
    avatar: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="头像URL"
    )
    # 权限与状态
    role: Mapped[str] = mapped_column(
        String(20), default="user", comment="权限级别: user, admin, owner"
    )
    is_banned: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否被封禁"
    )
    # 通用资产（很多插件都会用到的全局数值）
    level: Mapped[int] = mapped_column(Integer, default=1, comment="等级")
    exp: Mapped[int] = mapped_column(Integer, default=0, comment="经验值")
    coins: Mapped[int] = mapped_column(Integer, default=0, comment="金币/通用货币")
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), comment="首次交互时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=datetime.now,
        comment="最后更新时间",
    )

    groups: Mapped[list["UserGroup"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Group(Model):
    """群聊基本信息表"""

    __tablename__ = "bot_group"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, comment="QQ群号"
    )
    group_name: Mapped[str] = mapped_column(
        String(128), default="未知群聊", comment="群名称"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), onupdate=datetime.now
    )

    members: Mapped[list["UserGroup"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class UserGroup(Model):
    """用户与群聊的关联"""

    __tablename__ = "bot_user_group"

    # 设置联合唯一约束，防止同一个用户在同个群重复插入
    __table_args__ = (UniqueConstraint("user_id", "group_id", name="uix_user_group"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 外键关联
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("bot_user.user_id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("bot_group.group_id", ondelete="CASCADE"), index=True
    )

    # 群内专属信息
    nickname_in_group: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="群昵称"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否还在本群(退群后置为False)"
    )

    joined_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), comment="首次加群时间"
    )
    left_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="退群时间"
    )

    # 建立关系
    user: Mapped["User"] = relationship(back_populates="groups")
    group: Mapped["Group"] = relationship(back_populates="members")
