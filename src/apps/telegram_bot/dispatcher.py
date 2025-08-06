from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from settings import config
from apps.telegram_bot.handlers import start
from apps.telegram_bot.handlers import chat

bot = Bot(
    token=config.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode='Markdown')
)

dp = Dispatcher(storage=MemoryStorage())

dp.include_router(start.router)
dp.include_router(chat.router)