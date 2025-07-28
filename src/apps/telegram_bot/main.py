from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from aiogram import types

from settings import config
from apps.telegram_bot.dispatcher import dp, bot
from apps.telegram_bot.router import router as telegram_router
from apps.telegram_bot.commands.start import set_default_commands


@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot.set_webhook(config.WEBHOOK_URL)
    await set_default_commands(bot)
    yield
    await bot.delete_webhook()
    await bot.session.close()

app = FastAPI(lifespan=lifespan)
app.include_router(telegram_router)
