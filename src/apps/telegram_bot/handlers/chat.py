import asyncio
from aiogram import Router
from aiogram.types import Message
from aiogram.enums import ChatAction

from apps.knowledge_base.intent_router import IntentRouter
from db.session import async_session_maker
from apps.knowledge_base.services.faq_search import FAQSearch
from apps.knowledge_base.services.specs_search import SpecsSearch
from apps.knowledge_base.services.answer_service import AnswerService
from utils.telegram import delete_message
from utils.text import sanitize_telegram_html

router = Router()
intent_router = IntentRouter()
answer_service = AnswerService(model="gpt-4o")


async def keep_typing(message: Message, stop_event: asyncio.Event):
    while not stop_event.is_set():
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            continue


@router.message()
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
                data = await search.top_devices_json(user_message, top_n=10)
                context = "\n\n".join(
                    f"Модель: {m}\nОписание: {d}"
                    for m, d in zip(data["models"], data["descriptions"])
                )
            else:
                answer = await answer_service.fallback(user_message)
                await delete_message(typing_msg, delay=0)
                return await message.answer(sanitize_telegram_html(answer))

        answer = await answer_service.generate(user_message, context)

    finally:
        stop_event.set()
        typing_task.cancel()

    await delete_message(typing_msg, delay=0)
    await message.answer(sanitize_telegram_html(answer))