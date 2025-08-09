from aiogram import Router, F
from aiogram.types import Message

from apps.telegram_bot.services.voice_service import transcribe_voice
from apps.knowledge_base.services.alias_search import get_alias_search
from db.session import async_session_maker

router = Router()


@router.message(F.text | F.voice)
async def handle_user_message(message: Message):
    """
    Ищет упоминания моделей через Aho-Corasick и RapidFuzz и выводит найденные названия.
    """
    if message.text:
        prompt = message.text
    elif message.voice:
        prompt = await transcribe_voice(message)
    else:
        return

    placeholder = await message.answer("📝")

    try:
        async with async_session_maker() as session:
            service = await get_alias_search(session)
            models = service.find_models(prompt, top_k=10)

        if models:
            reply = "Найдено:\n" + "\n".join(f"• {m}" for m in models)
        else:
            reply = "Ничего не нашлось"

        await placeholder.edit_text(reply)
    except Exception:
        await placeholder.edit_text("⚠️ Что‑то пошло не так. Попробуй ещё раз.")
