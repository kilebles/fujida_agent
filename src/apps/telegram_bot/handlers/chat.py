from aiogram import Router
from aiogram.types import Message
from apps.knowledge_base.intent_router import IntentRouter
from db.session import async_session_maker
from apps.knowledge_base.services.faq_search import FAQSearch
from apps.knowledge_base.services.specs_search import SpecsSearch
from apps.knowledge_base.services.answer_service import AnswerService

router = Router()
intent_router = IntentRouter()
answer_service = AnswerService(model="gpt-4o")


@router.message()
async def handle_chat(message: Message):
    user_message = message.text.strip()
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
            await message.answer("Этот вопрос не относится к FAQ или устройствам 🙃")
            return

    answer = await answer_service.generate(user_message, context)
    await message.answer(answer)