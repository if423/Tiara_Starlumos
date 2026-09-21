import nonebot

async def get_plugins():
    plugins: set[Plugin] = nonebot.get_loaded_plugins()
    message = ""
    for plugin in plugins:
        message += f"{plugin.name}\n"
        if plugin.metadata:
            desc = plugin.metadata.description if plugin.metadata else ""
            usage = plugin.metadata.usage if plugin.metadata.usage else ""
            message += f"{desc}\n{usage}\n"
        message += f"\n\n"
        
    return message

