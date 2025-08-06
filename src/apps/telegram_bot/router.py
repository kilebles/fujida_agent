import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from aiogram import types

from apps.telegram_bot.dispatcher import bot, dp

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        logger.info("RAW UPDATE: %s", data)
        update = types.Update(**data)
        await dp.feed_update(bot=bot, update=update)
        return {"ok": True}
    except ValidationError as ve:
        logger.warning("VALIDATION ERROR: %s", ve)
        return JSONResponse(status_code=400, content={"error": "ValidationError", "details": str(ve)})
    except Exception as e:
        logger.error("GENERAL ERROR: %s", e)
        return JSONResponse(status_code=500, content={"error": "InternalServerError", "details": str(e)})
