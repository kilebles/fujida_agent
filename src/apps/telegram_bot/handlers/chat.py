import asyncio
from aiogram import Router
from aiogram.types import Message
from aiogram.enums import ChatAction
from aiogram.filters import Command

from apps.knowledge_base.intent_router import IntentRouter
from db.session import async_session_maker
from apps.knowledge_base.services.faq_search import FAQSearch
from apps.knowledge_base.services.specs_search import SpecsSearch
from apps.knowledge_base.services.answer_service import AnswerService
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
    msg = user_message.lower()
    selected = []
    for m, d, a in zip(models, descriptions, aliases):
        names = [m.lower()] + [al.lower() for al in (a or [])]
        if any(name in msg for name in names):
            selected.append((m, d))
    return selected


@router.message(~Command(commands=["start", "help"]))
async def handle_chat(message: Message):
    user_message = message.text.strip()
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
                        f"Модель: {m}\nОписание: {d}"
                        for m, d in selected
                    )
                else:
                    context = "\n\n".join(
                        f"Модель: {m}\nОписание: {d}"
                        for m, d in zip(data["models"][:7], data["descriptions"][:7])
                    )
            else:
                answer = await answer_service.fallback(user_message)
                await delete_message(typing_msg, delay=0)
                return await message.answer(sanitize_telegram_html(answer))

        answer = await answer_service.generate(user_message, context, intent)

    finally:
        stop_event.set()
        typing_task.cancel()

    await delete_message(typing_msg, delay=0)
    await message.answer(sanitize_telegram_html(answer))

    try:
        sheets_logger.log_message(user_message, answer, source="telegram")
    except Exception as e:
        logger.error("Ошибка логирования в Google Sheets", exc_info=e)