import json
import logging

from aiogram import Router, F
from aiogram.types import Message
from apps.telegram_bot.services.voice_service import transcribe_voice
from apps.knowledge_base.intent_router import route_intent_llm

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text | F.voice)
async def handle_user_message(message: Message) -> None:
    try:
        user_prompt = message.text or await transcribe_voice(message)
        result = await route_intent_llm(user_prompt)
        await message.answer(
            f"```json\n{json.dumps(result, ensure_ascii=False, indent=2)}\n```",
        )
    except Exception as e:
        logger.exception('Handler error')
        await message.answer(f'Ошибка: {type(e).__name__}: {e}')
