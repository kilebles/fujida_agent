import json
import asyncio
import logging

from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import async_session_maker
from db.models.devices import Device
from common.openai_client import openai_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

JSON_PATH = Path('src/common/devices.json')


def clean_text(text: str | None) -> str:
    if not text:
        return ''
    value = str(text).strip()
    return value if value.lower() != 'nan' else ''


def build_embedding_input(model: str, description: str) -> str:
    return f"Модель: {model}\nОписание: {description}"


async def get_embedding(text: str) -> list[float]:
    response = await openai_client.embeddings.create(
        input=text,
        model="text-embedding-3-large"
    )
    return response.data[0].embedding


async def import_devices():
    logging.info("Начат импорт моделей устройств из JSON")

    with JSON_PATH.open('r', encoding='utf-8') as f:
        data = json.load(f)

    async with async_session_maker() as session:
        for entry in data:
            model = clean_text(entry.get('model'))
            description = clean_text(entry.get('description'))
            information = entry.get('information') or {}

            if not model:
                logging.warning("Пропущена модель без названия")
                continue

            result = await session.execute(
                select(Device).where(Device.model == model)
            )
            existing = result.scalar_one_or_none()

            input_text = build_embedding_input(model, description)
            embedding = await get_embedding(input_text)

            if existing:
                logging.info(f"Обновляется модель: {model}")
                existing.description = description
                existing.information = information
                existing.embedding = embedding
            else:
                device = Device(
                    model=model,
                    description=description,
                    information=information,
                    embedding=embedding
                )
                session.add(device)
                logging.info(f"Добавлена новая модель: {model}")

        await session.commit()
        logging.info("Импорт моделей завершён")


if __name__ == '__main__':
    asyncio.run(import_devices())
