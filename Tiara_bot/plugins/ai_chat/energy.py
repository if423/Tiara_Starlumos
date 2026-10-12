import logging
import time

from nonebot_plugin_orm import async_scoped_session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .config import config
from .models import ChatEnergy

logger = logging.getLogger("ai_chat.energy")


async def get_or_create_energy(
    session: async_scoped_session,
    group_id: str,
) -> ChatEnergy:
    """获取或创建群能量记录。

    同一群的两条消息并发首次创建时会撞上 group_id 唯一约束，
    这里回滚后复用已存在的记录，避免抛错打断正常回复。
    """
    stmt = select(ChatEnergy).where(ChatEnergy.group_id == group_id)
    record = await session.scalar(stmt)
    if record is not None:
        return record

    record = ChatEnergy(group_id=group_id, energy=config.energy_max)
    session.add(record)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        record = await session.scalar(stmt)
        if record is None:
            raise
        return record

    await session.refresh(record)
    return record


async def _apply_recovery(
    session: async_scoped_session,
    record: ChatEnergy,
) -> float:
    """按离线时长恢复能量并返回恢复后的值（内部函数，复用已取到的记录）。"""
    now = int(time.time())

    if record.last_recovery <= 0:
        record.last_recovery = now
        energy = record.energy  # 提交前取出，避免访问已过期属性
        await session.commit()
        return energy

    elapsed_seconds = max(0, now - record.last_recovery)
    recovery = elapsed_seconds / 60.0 * config.energy_recovery_per_minute
    if recovery <= 0:
        return record.energy

    energy = min(config.energy_max, record.energy + recovery)
    record.energy = energy
    record.last_recovery = now
    await session.commit()
    return energy


async def recover_energy(
    session: async_scoped_session,
    group_id: str,
) -> float:
    """按离线时长恢复能量，返回当前能量。"""
    record = await get_or_create_energy(session, group_id)
    return await _apply_recovery(session, record)


async def consume_energy(
    session: async_scoped_session,
    group_id: str,
    reply_length: int,
) -> float:
    """按回复长度消耗能量，返回剩余能量。"""
    record = await get_or_create_energy(session, group_id)

    cost = config.energy_cost_short if reply_length < 50 else config.energy_cost_long
    energy = max(0.0, record.energy - cost)
    record.energy = energy
    await session.commit()

    logger.debug(
        "Energy consumed: group=%s cost=%.2f remaining=%.2f",
        group_id,
        cost,
        energy,
    )
    return energy


async def can_proactive_reply(
    session: async_scoped_session,
    group_id: str,
) -> bool:
    """检查是否允许主动回复（冷却 + 能量阈值）。"""
    record = await get_or_create_energy(session, group_id)

    now = int(time.time())
    if now - record.last_proactive_reply < config.proactive_cooldown_seconds:
        return False

    # 只查一次记录，恢复逻辑复用同一条
    energy = await _apply_recovery(session, record)
    return energy >= config.energy_threshold_smile


async def mark_proactive_reply(
    session: async_scoped_session,
    group_id: str,
) -> None:
    """更新上次主动回复时间戳。"""
    record = await get_or_create_energy(session, group_id)

    now = int(time.time())
    if record.last_proactive_reply == now:
        return

    record.last_proactive_reply = now
    await session.commit()


async def update_bot_state(
    session: async_scoped_session,
    group_id: str,
    state: str,
) -> None:
    """更新状态机字段（状态未变化时不写库）。"""
    record = await get_or_create_energy(session, group_id)
    if record.bot_state == state:
        return

    record.bot_state = state
    await session.commit()
    logger.debug("Bot state: group=%s state=%s", group_id, state)
