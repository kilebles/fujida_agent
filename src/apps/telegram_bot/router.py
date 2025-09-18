from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from aiogram import types

from apps.telegram_bot.dispatcher import bot, dp
from logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        logger.info("Telegram update received")
        update = types.Update(**data)
        await dp.feed_update(bot=bot, update=update)
        return {"ok": True}
    except ValidationError as ve:
        logger.warning("Validation error: %s", ve)
        return JSONResponse(status_code=400, content={"error": "ValidationError", "details": str(ve)})
    except Exception as e:
        logger.error("Unhandled error: %s", e)
        return JSONResponse(status_code=500, content={"error": "InternalServerError", "details": str(e)})