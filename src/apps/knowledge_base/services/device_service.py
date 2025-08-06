import json

from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, cast
from pgvector.sqlalchemy import Vector

from db.models.devices import Device
from db.session import async_session_maker
from common.openai_client import openai_client
from apps.knowledge_base.prompt_template import build_knowledge_prompt


def extract_model_names(user_message: str, known_models: List[str]) -> List[str]:
    """
    Выделяет явно упомянутые модели из текста.
    """
    message_lower = user_message.lower()
    return [m for m in known_models if m.lower() in message_lower]


async def search_devices_by_semantics(query: str, session: AsyncSession, top_n: int = 5) -> List[Device]:
    embedding_response = await openai_client.embeddings.create(
        input=query,
        model="text-embedding-3-large"
    )
    embedding = embedding_response.data[0].embedding

    stmt = (
        select(Device)
        .order_by(func.cosine_distance(Device.embedding, cast(embedding, Vector)))
        .limit(top_n)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


def build_context(devices: list[Device]) -> str:
    def format_info(info: dict) -> str:
        return "\n".join(f"- *{key}*: {value}" for key, value in info.items())

    return "\n\n".join(
        f"{device.model}\n\n"
        f"{device.description}\n\n"
        f"{format_info(device.information)}"
        for device in devices
    )

async def generate_device_response(user_message: str) -> str:
    """
    Возвращает ответ на вопрос пользователя о моделях Fujida.
    """
    async with async_session_maker() as session:
        all_models_result = await session.execute(select(Device.model))
        all_models = [m[0] for m in all_models_result.all()]

        mentioned_models = extract_model_names(user_message, all_models)

        if len(mentioned_models) >= 2:
            stmt = select(Device).where(Device.model.in_(mentioned_models))
            result = await session.execute(stmt)
            devices = result.scalars().all()

            context = "\n\n".join(
                f"{d.model}:\n{d.description}\nХарактеристики: {json.dumps(d.information, ensure_ascii=False)}"
                for d in devices
            )

        else:
            devices = await search_devices_by_semantics(user_message, session)
            context = "\n\n".join(f"{d.model}:\n{d.description}" for d in devices)

    prompt = build_knowledge_prompt(context, user_message)

    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content
