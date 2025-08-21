import logging

from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender

from apps.telegram_bot.services.voice_service import transcribe_voice
from apps.knowledge_base.intent_router import route_intent_llm
from apps.knowledge_base.prompt_template import build_prompt_for_router_payload
from utils.text import strip_empty_fields
from common.openai_client import ensure_openai_client

logger = logging.getLogger(__name__)
router = Router()


def split_message(text: str, limit: int = 4000) -> list[str]:
    parts: list[str] = []
    while text:
        parts.append(text[:limit])
        text = text[limit:]
    return parts


@router.message(F.text | F.voice)
async def handle_user_message(message: Message) -> None:
    try:
        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            user_prompt = message.text or await transcribe_voice(message)
            result = await route_intent_llm(user_prompt)

            clean = strip_empty_fields({**result, "user_query": result.get("user_query") or user_prompt})
            prompt = build_prompt_for_router_payload(clean)

            client = await ensure_openai_client()
            resp = await client.chat.completions.create(
                model="gpt-5-mini",
                messages=[{"role": "user", "content": prompt}],
            )
            final_answer = resp.choices[0].message.content or ""
            for chunk in split_message(final_answer):
                await message.answer(chunk)
    except Exception as e:
        logger.exception("Handler error")
        await message.answer(f"Ошибка: {type(e).__name__}: {e}")
