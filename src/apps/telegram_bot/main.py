from contextlib import asynccontextmanager

from fastapi import FastAPI

from settings import config
from apps.telegram_bot.dispatcher import bot
from apps.telegram_bot.router import router as telegram_router
from apps.telegram_bot.commands.commands import set_default_commands
from logger import setup_logging, get_logger
from logger.middlewares.fastapi import RequestContextMiddleware, AccessLogMiddleware
from common.openai_client import init_openai_client, warmup_openai, close_openai_client

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_openai_client()
    await warmup_openai()
    logger.info("Setting webhook to: %s", config.WEBHOOK_URL)
    await bot.set_webhook(config.WEBHOOK_URL)
    await set_default_commands(bot)
    yield
    logger.info("Shutting down, deleting webhook")
    await bot.delete_webhook()
    await bot.session.close()
    await close_openai_client()


app = FastAPI(lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(AccessLogMiddleware)
app.include_router(telegram_router)
