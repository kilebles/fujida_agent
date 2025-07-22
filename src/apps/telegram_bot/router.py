from fastapi import APIRouter, Request
from aiogram import types

from .dispatcher import bot, dp

router = APIRouter()


@router.post("/")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot=bot, update=update)
    return {"ok": True}