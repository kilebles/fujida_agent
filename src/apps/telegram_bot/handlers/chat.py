import logging

from aiogram import Router, F
from aiogram.types import Message

from apps.knowledge_base.services.alias_search import get_alias_search
from apps.knowledge_base.services.search_gateway import SearchGateway
from apps.knowledge_base.services.vector_search import VectorSearchService
from apps.telegram_bot.services.voice_service import transcribe_voice
from db.session import async_session_maker


logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text | F.voice)
async def handle_user_message(message: Message):
    """
    Выполняет поиск моделей через alias и векторный фолбэк.
    Если ничего не найдено, выполняет чисто векторный поиск без порога.
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
            alias_service = await get_alias_search(session)
            gateway = SearchGateway(alias_service, session)
            vector_service = VectorSearchService(session)

            async def vector_cb(q: str, k: int) -> list[str]:
                return await vector_service.topk(q, top_k=k, min_similarity=0.72, probes=10)

            result = await gateway.search(prompt, vector_fn=vector_cb, top_k=10)

            models = list(result.models)
            source = "alias+vector" if result.used_vector else "alias"

            if not models:
                vector_only = await vector_service.topk(prompt, top_k=10, min_similarity=None, probes=20)
                if vector_only:
                    models = vector_only
                    source = "vector"

        if models:
            reply = "Найдено:\n" + "\n".join(f"• {m}" for m in models) + f"\n\n[{source}]"
        else:
            reply = "Ничего не нашлось"

        await placeholder.edit_text(reply)
    except Exception:
        logger.exception("Search failed")
        await placeholder.edit_text("⚠️ Что-то пошло не так. Попробуй ещё раз.")
