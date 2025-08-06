from aiogram import Router, F
from aiogram.types import Message

from apps.knowledge_base.intent_router import handle_knowledge_query
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

    placeholder = await message.answer("📝")

    reply = await handle_knowledge_query(prompt)

    try:
        await placeholder.edit_text(reply)
    except Exception:
        await placeholder.edit_text("⚠️ Не удалось отобразить ответ, попробуйте снова.")
