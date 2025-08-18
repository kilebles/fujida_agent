from contextlib import asynccontextmanager

from fastapi import FastAPI

from settings import config
from apps.telegram_bot.dispatcher import dp, bot
from apps.telegram_bot.router import router as telegram_router
from apps.telegram_bot.commands.start import set_default_commands
from logger import setup_logging, get_logger
from logger.middlewares.fastapi import RequestContextMiddleware, AccessLogMiddleware

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Setting webhook to: %s", config.WEBHOOK_URL)
    await bot.set_webhook(config.WEBHOOK_URL)
    await set_default_commands(bot)
    yield
    logger.info("Shutting down, deleting webhook")
    await bot.delete_webhook()
    await bot.session.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(AccessLogMiddleware)
app.include_router(telegram_router)
