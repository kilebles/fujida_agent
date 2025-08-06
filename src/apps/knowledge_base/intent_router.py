from common.openai_client import openai_client

from db.models.devices import Device
from db.session import async_session_maker
from apps.knowledge_base.services.faq_service import search_similar_faqs, build_context as build_faq_context
from apps.knowledge_base.services.device_service import search_devices_by_semantics, build_context as build_device_context
from apps.knowledge_base.prompt_template import build_knowledge_prompt


async def handle_knowledge_query(user_message: str) -> str:
    """
    Универсальный вход: определяет intent и формирует ответ.
    """
    intent_prompt = (
        "Ты классификатор запроса. Ответь строго: faq или device.\n"
        "faq — если вопрос про настройку, гарантию, обновление и т.п.\n"
        "device — если пользователь хочет подобрать или сравнить устройства Fujida.\n\n"
        f"Запрос: {user_message}"
    )

    intent_response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": intent_prompt}],
        temperature=0
    )
    intent = intent_response.choices[0].message.content.strip().lower()
    if intent not in {"faq", "device"}:
        intent = "faq"

    embedding_response = await openai_client.embeddings.create(
        input=user_message,
        model="text-embedding-3-large"
    )
    embedding = embedding_response.data[0].embedding

    async with async_session_maker() as session:
        if intent == "device":
            devices = await search_devices_by_semantics(user_message, session)
            context = build_device_context(devices)
        else:
            faqs = await search_similar_faqs(embedding, session)
            context = await build_faq_context(faqs)

    prompt = build_knowledge_prompt(context, user_message)
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
