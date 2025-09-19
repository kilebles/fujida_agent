import asyncio
from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ChatAction

from apps.knowledge_base.intent_router import IntentRouter
from db.session import async_session_maker
from apps.knowledge_base.services.faq_search import FAQSearch
from apps.knowledge_base.services.specs_search import SpecsSearch, normalize_text
from apps.knowledge_base.services.answer_service import AnswerService
from apps.telegram_bot.services.voice_service import transcribe_voice
from utils.telegram import delete_message
from utils.text import sanitize_telegram_html
from utils.google_sheets import GoogleSheetsLogger
from logger.config import get_logger

router = Router()
intent_router = IntentRouter()
answer_service = AnswerService(model="gpt-4o")
sheets_logger = GoogleSheetsLogger()
logger = get_logger(__name__)


async def keep_typing(message: Message, stop_event: asyncio.Event):
    while not stop_event.is_set():
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            continue


def filter_models(user_message: str, models: list[str], descriptions: list[str], aliases: list[list[str]]):
    msg = normalize_text(user_message)
    selected = []
    for m, d, a in zip(models, descriptions, aliases):
        names = [normalize_text(m)] + [normalize_text(al) for al in (a or [])]
        if any(name in msg for name in names):
            selected.append((m, d, a))
    return selected


@router.message(F.text | F.voice)
async def handle_chat(message: Message):
    if message.text:
        user_message = message.text.strip()
    elif message.voice:
        try:
            user_message = await transcribe_voice(message)
        except Exception as e:
            logger.error("Ошибка транскрибации голоса", exc_info=e)
            return await message.answer("❌ Не удалось распознать голосовое сообщение")
    else:
        return await message.answer("❌ Сообщение не распознано")

    typing_msg = await message.answer("📝")
    stop_event = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(message, stop_event))

    try:
        intent = await intent_router.classify(user_message)

        async with async_session_maker() as session:
            if intent == "FAQ":
                search = FAQSearch(session)
                data = await search.top_faq_json(user_message, top_n=3)
                context = "\n\n".join(
                    f"Q: {q}\nA: {a}"
                    for q, a in zip(data["top_questions"], data["top_answers"])
                )
            elif intent == "Device":
                search = SpecsSearch(session)
                data = await search.top_devices_json(user_message, top_n=15)

                selected = filter_models(
                    user_message,
                    data["models"],
                    data["descriptions"],
                    data["aliases"],
                )

                if selected:
                    context = "\n\n".join(
                        f"Модель: {m}\nАлиасы: {', '.join(a or [])}\nОписание: {d}"
                        for m, d, a in selected
                    )
                else:
                    context = "\n\n".join(
                        f"Модель: {m}\nАлиасы: {', '.join(a or [])}\nОписание: {d}"
                        for m, d, a in zip(
                            data["models"][:7],
                            data["descriptions"][:7],
                            data["aliases"][:7],
                        )
                    )
            else:
                answer = await answer_service.fallback(user_message)
                await delete_message(typing_msg, delay=0)
                return await message.answer(sanitize_telegram_html(answer))

        answer = await answer_service.generate(user_message, context, intent)

    except Exception as e:
        logger.error("Ошибка обработки сообщения", exc_info=e)
        answer = "⚠️ Что-то пошло не так. Попробуй ещё раз."
    finally:
        stop_event.set()
        typing_task.cancel()

    await delete_message(typing_msg, delay=0)
    await message.answer(sanitize_telegram_html(answer))

    try:
        sheets_logger.log_message(user_message, answer, source="telegram")
    except Exception as e:
        logger.error("Ошибка логирования в Google Sheets", exc_info=e)