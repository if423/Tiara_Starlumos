from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.rule import to_me

weather = on_command(
    "天气", rule=to_me(), aliases={"weather", "查天气"}, priority=9, block=True
)


@weather.handle()
async def handle_function(args: Message = CommandArg()):
    # await weather.send("天气是...")
    # await weather.finish("天气是...")
    if location := args.extract_plain_text():
        await weather.finish(f"今天{location}的天气是...")
    else:
        await weather.finish("请输入地名")
