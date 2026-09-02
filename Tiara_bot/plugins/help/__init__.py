from nonebot import get_plugin_config, on_command
from nonebot.adapters import Event, Message
from nonebot.params import CommandArg
from nonebot.rule import Rule, to_me

from .config import Config

plugin_config = get_plugin_config(Config).bot_help


# 是否启用
async def is_enadle() -> bool:
    return plugin_config.plugin_enabled


# 用户是否在黑名单
async def is_blacklisted(event: Event) -> bool:
    return True  # event.get_user_id() not in BLACKLIST


bot_help = on_command(
    "帮助",
    rule=to_me() & is_enadle & is_blacklisted,
    aliases={"help", "使用帮助"},
    priority=plugin_config.command_priority,
    block=True,
)


@bot_help.handle()
async def handle_function(args: Message = CommandArg()):
    if location := args.extract_plain_text():
        await bot_help.finish(f"")
    else:
        await bot_help.finish("这里是帮助菜单,但是还没写")
