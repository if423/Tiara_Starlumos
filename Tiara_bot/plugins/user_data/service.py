import pytz
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from nonebot_plugin_orm import async_scoped_session

from .models import User, Group, UserGroup


async def user_updata(
        session: async_scoped_session,
        user_id: int | str,
        nickname: str,
        avatar: str | None = None,
        group_id: int | str = 0,
        group_name: str = "private",
        nickname_in_group: str | None = None
) -> Tuple[User, Group, UserGroup]:
    user_id = int(user_id)
    group_id = int(group_id)

    has_changes = False

    stmt_user = select(User).where(User.user_id == user_id)
    user = await session.scalar(stmt_user)

    if not user:
        user = User(user_id=user_id, nickname=nickname, avatar=avatar)
        session.add(user)
        has_changes = True
    else:
        if nickname and user.nickname != nickname:
            user.nickname = nickname
            has_changes = True
        if avatar and user.avatar != avatar:
            user.avatar = avatar
            has_changes = True
    
    stmt_group = select(Group).where(Group.group_id == group_id)
    group = await session.scalar(stmt_group)

    if not group:
        group = Group(group_id=group_id, group_name=group_name)
        session.add(group)
        has_changes = True
    else:
        if group_name and group.group_name != group_name:
            group.group_name = group_name
            has_changes = True

    stmt_ug = select(UserGroup).where(UserGroup.user_id == user_id, UserGroup.group_id == group_id)
    user_group = await session.scalar(stmt_ug)

    current_card = nickname_in_group or nickname

    if not user_group:
        user_group = UserGroup(
            user_id=user_id,
            group_id=group_id,
            nickname_in_group=current_card,
            is_active=True,
            joined_at=datetime.now(pytz.timezone("Asia/Shanghai"))
        )
        session.add(user_group)
        has_changes = True
    else:
        if current_card and current_card != user_group.nickname_in_group:
            user_group.nickname_in_group = current_card
            has_changes = True

    if has_changes:
        try:
            await session.commit()

            await session.refresh(user)
            await session.refresh(group)
            await session.refresh(user_group)

        except IntegrityError:
            await session.rollback()

            user = await session.scalar(stmt_user)
            group = await session.scalar(stmt_group)
            user_group = await session.scalar(stmt_ug)

    return user, group, user_group
        
async def member_added(user_id: int | str, group_id: int | str):
    user_id = int(user_id)
    group_id = int(group_id)

    stmt_ug = select(UserGroup).where(UserGroup.user_id == user_id, UserGroup.group_id == group_id)
    user_group = await session.scalar(stm_ug)

    if user_group:
        if not user_group.is_active:
            user_group.is_active = True
            user_group.left_at = None
            user_group.joined_at = datetime.now(pytz.timezone("Asia/Shanghai"))

            await session.commit()

async def member_removed(user_id: int | str, group_id: int | str):
    user_id = int(user_id)
    group_id = int(group_id)

    stmt_ug = select(UserGroup).where(UserGroup.user_id == usser_id, UserGroup.group_id == group_id)
    user_group = await session.scalar(stm_ug)

    if user_group:
        if user_group.is_active:
            user_group.is_active = False
            user_group.left_at = datetime.now(pytz.timezone("Asia/Shanghai"))
            user_group.joined_at = None
            
            await session.commit()

