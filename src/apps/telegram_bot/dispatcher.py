from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from settings import config
from apps.telegram_bot.handlers import start
from apps.telegram_bot.handlers import chat
from logger.middlewares.aiogram import TelegramContextMiddleware

bot = Bot(
    token=config.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML"),
)

dp = Dispatcher(storage=MemoryStorage())
dp.update.outer_middleware(TelegramContextMiddleware())

dp.include_router(start.router)
dp.include_router(chat.router)
