from aiogram import Bot
from aiogram.types import BotCommand


async def set_default_commands(bot: Bot):
    commands = [
        BotCommand(command='start', description='Старт'),
        BotCommand(command='help', description='Обратиться в поддержку')
    ]
    
    await bot.set_my_commands(commands)