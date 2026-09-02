from nonebot import on_fullmatch
from nonebot.adapters import Bot, Event
from nonebot.plugin import PluginMetadata
from nonebot.rule import Rule

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="签到",
    description="每日签到获得金币",
    usage="发送'签到'进行签到",
    type="application",
    config=Config,
    extra={},
)

sign = on_fullmatch(
    ("签到", "sign", "每日签到"),
    priority=9,
    block=True,
)


@sign.handle()
async def hand_function(bot: Bot, event: Event):
    user_id = event.get_user_id()
    user = event.user
    user_name = user.nick or user.name
    await sign.finish(f"{user_name}签到成功(其实还在写,但是我说成功就是成功了)")
