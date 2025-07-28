from aiogram import Router, F, types
from aiogram.types import Message

from apps.telegram_bot.services.openai_service import generate_response
from apps.telegram_bot.services.voice_service import transcribe_voice

router = Router()


@router.message(F.text | F.voice)
async def handle_user_message(message: Message):
    if message.text:
        prompt = message.text
    elif message.voice:
        prompt = await transcribe_voice(message)
    else:
        return

    reply = await generate_response(prompt)
    await message.answer(reply)