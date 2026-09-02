import nonebot

# from nonebot.adapters.bilibili import Adapter as BillBillAdapter
from nonebot.adapters.bilibili_live import Adapter as BillBill_liveAdapter

# from nonebot.adapters.console import Adapter as ConsoleAdapter
from nonebot.adapters.satori import Adapter as SatoriAdapter  # 避免重复命名

# 初始化 NoneBot
nonebot.init(_env_file=".env")

# 注册适配器
driver = nonebot.get_driver()
# driver.register_adapter(BillBillAdapter)
driver.register_adapter(BillBill_liveAdapter)
# driver.register_adapter(ConsoleAdapter)
driver.register_adapter(SatoriAdapter)

# 在这里加载插件
nonebot.load_builtin_plugins("echo")  # 内置插件
# nonebot.load_plugin("thirdparty_plugin")  # 第三方插件
# nonebot.load_plugins("Tiara_bot/plugins")  # 马巨擘
nonebot.load_plugins("Tiara_bot/plugins")  # 亚述巴尼拔
# nonebot.load_plugins("Tiara_bot/plugins")  # 尼禄

if __name__ == "__main__":
    nonebot.run()
