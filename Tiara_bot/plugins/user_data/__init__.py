from nonebot import require, on, on_command, on_notice, logger

require("nonebot_plugin_localstore")
require("nonebot_plugin_orm")

from nonebot.adapters.satori import Bot, MessageEvent, Message
from nonebot.plugin import PluginMetadata
from nonebot.adapters.satori.event import (
    GuildMemberAddedEvent,
    GuildMemberRemovedEvent
)

from nonebot_plugin_orm import async_scoped_session
from . import models
from .service import user_updata, member_add, member_remove

__plugin_meta__ = PluginMetadata(
    name="user_data",
    description="获取用户数据存储到数据库",
    usage="",
    type="data",
    extra={}
)

user_data = on(priority=99, block=False)

# user_data = on_command("我的信息", priority=10, block=True)

@user_data.handle()
async def handle_function(bot: Bot, event: MessageEvent, session: async_scoped_session):
    try:
        group = event.guild
        group_id = "0"
        group_name = "private"
        group_user_name = None
        if group != None:
            group_id = group.id                 # 群id
            group_name = group.name             # 群名
            group_user = event.member
            group_user_name = group_user.nick   # 用户群昵称
        user = event.user
        user_id = user.id                       # 用户id
        user_name = user.nick or user.name      # 用户昵称
        user_avatar = user.avatar               # 用户头像url路径

        await user_updata(session, user_id, user_name, user_avatar, group_id, group_name, group_user_name)

        # await user_data.finish(f"{user_id}\n{user_name}\n{user_avatar}\n{group_id}\n{group_name}\n{group_user_name}")

    except Exception as e:
        logger.error(f"用户/群组信息同步失败:{e}")

async def get_user_name(bot: Bot, user_id: str) -> str:
    """通过 Satori API 获取用户昵称，失败时回退到用户 ID"""
    try:
        user: User = await bot.user_get(user_id=user_id)
        return user.nick or user.name or user.id
    except Exception as e:
        logger.warning(f"获取用户 {user_id} 信息失败: {e}")
        return user_id

# 监听群成员加入事件
member_added = on_notice(rule=lambda event: isinstance(event, GuildMemberAddedEvent))

@member_added.handle()
async def handle_member_added(bot: Bot, event: GuildMemberAddedEvent, session: async_scoped_session):
    user = event.user
    guild = event.guild
    name = await get_user_name(bot, user.id)
    await member_add(session, user.id, guild.id)
    msg = f"欢迎新成员 {name} (ID: {user.id}) 加入群组！"
    await bot.send_message(guild.id, msg)

# 监听群成员退出事件
member_removed = on_notice(rule=lambda event: isinstance(event, GuildMemberRemovedEvent))

@member_removed.handle()
async def handle_member_removed(bot: Bot, event: GuildMemberRemovedEvent, session: async_scoped_session):
    user = event.user
    guild = event.guild
    name = await get_user_name(bot, user.id)
    await member_remove(session, user.id, guild.id)
    msg = f"成员 {name} (ID: {user.id}) 离开了群组!"
    await bot.send_message(guild.id, msg)
    