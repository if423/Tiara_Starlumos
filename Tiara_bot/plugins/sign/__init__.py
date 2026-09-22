from nonebot import require

require("nonebot_plugin_localstore")
require("nonebot_plugin_orm")

from nonebot import on_command
from nonebot.adapters.satori import Bot, MessageEvent
from nonebot.plugin import PluginMetadata

from nonebot_plugin_orm import async_scoped_session
from .config import Config
from .service import get_sign_in
from . import models

__plugin_meta__ = PluginMetadata(
    name="sign",
    description="每日签到获得金币",
    usage="发送'签到'进行签到",
    type="application",
    config=Config,
    extra={},
)

sign = on_command(
    "签到",
    aliases={"sign", "每日签到"},
    priority=9,
    block=True,
)


@sign.handle()
async def hand_function(bot: Bot, event: MessageEvent, session: async_scoped_session):
    group = event.guild
    group_id = ""
    group_name = ""
    if group != None:
        group_id = group.id
        group_name = group.name
    user = event.user
    user_id = user.id
    user_name = user.nick or user.name

    if location := event.message.content.rstrip(r"签到|sign|每日签到"):
        if "排行" in location:
            get_sign_ranking(group_id=group_id)
        else:
            pass

    else:
        image = await get_sign_in(session, int(user_id))
        await sign.finish(f"用户{user_name}{image}")
