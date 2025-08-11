import json
import logging

from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender

from apps.knowledge_base.services.alias_search import get_alias_search
from apps.knowledge_base.services.search_gateway import SearchGateway
from apps.knowledge_base.services.vector_search import VectorSearchService
from apps.knowledge_base.services.device_repo import DeviceRepo
from apps.knowledge_base.prompt_template import (
    instructions_text,
    build_context_message,
)
from apps.telegram_bot.services.voice_service import transcribe_voice
from db.session import async_session_maker
from common.openai_client import openai_client


logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text | F.voice)
async def handle_user_message(message: Message):
    """
    Формирует контекст по найденным моделям и их характеристикам и запрашивает ответ у LLM через Responses API.
    """
    if message.text:
        user_prompt = message.text
    elif message.voice:
        user_prompt = await transcribe_voice(message)
    else:
        return

    try:
        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            async with async_session_maker() as session:
                alias_service = await get_alias_search(session)
                gateway = SearchGateway(alias_service, session)
                vector_service = VectorSearchService(session)
                repo = DeviceRepo(session)

                async def vector_cb(q: str, k: int) -> list[str]:
                    return await vector_service.topk(
                        q,
                        top_k=k,
                        min_similarity=0.72,
                        probes=10,
                    )

                result = await gateway.search(
                    user_prompt,
                    vector_fn=vector_cb,
                    top_k=10,
                )
                models = list(result.models)
                if not models:
                    models = await vector_service.topk(
                        user_prompt,
                        top_k=10,
                        min_similarity=None,
                        probes=20,
                    )

                devices = await repo.get_by_models(models[:10])

                ctx_items = [
                    {
                        "model": d.model,
                        "description": d.description or "",
                        "information": d.information,
                    }
                    for d in devices
                ]
                context = json.dumps(
                    ctx_items,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                dev_msg = build_context_message(context)

                resp = await openai_client.responses.create(
                    model="gpt-5-2025-08-07",
                    reasoning={"effort": "low"},
                    instructions=instructions_text(),
                    input=[
                        {"role": "developer", "content": dev_msg},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_output_tokens=1500,
                )
                answer = resp.output_text or "Не смог сформировать ответ."

        await message.answer(answer)
    except Exception:
        logger.exception("LLM answer failed")
        await message.answer("⚠️ Что-то пошло не так. Попробуй ещё раз.")
