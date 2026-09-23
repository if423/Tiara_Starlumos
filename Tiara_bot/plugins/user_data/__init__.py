from nonebot import require, on, on_command, on_notice, logger

require("nonebot_plugin_localstore")
require("nonebot_plugin_orm")

from nonebot.adapters.satori import Bot, MessageEvent, Message
from nonebot.plugin import PluginMetadata
from nonebto.adapters.satori.event import (
    GuildMemberAddedEvent,
    GuildMemberRemoveEvent
)

from nonebot_plugin_orm import async_scoped_session
from . import models
from .service import user_updata, member_added, member_removed

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

# 监听群成员加入事件
member_added = on_notice(rule=lambda event: isinstance(event, GuildMemberAddedEvent))

@member_added.handle()
async def handle_member_added(bot: Bot, event: GuildMemberAddedEvent):
    user = event.user
    guild = event.guild
    member_added()
    await member_added.send(f"欢迎新成员 {user.name} (ID: {user.id}) 加入群组 {guild.name}!")

# 监听群成员退出事件
member_removed = on_notice(rule=lambda event: isinstance(event, GuildMemberRemovedEvent))

@member_removed.handle()
async def handle_member_removed(bot: Bot, event: GuildMemberRemovedEvent):
    user = event.user
    operator = event.operator  # 执行移除操作的用户（如果是主动退群，可能与 user 相同）
    guild = event.guild
    member_removed()
    await bot.send(f"成员 {user.name} (ID: {user.id}) 离开了群组 {guild.name}。"f"操作者: {operator.name if operator else '未知'}")
