import json
import asyncio
import logging

from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import async_session_maker
from utils.text import normalize
from db.models.devices import Device, DeviceAlias
from common.openai_client import openai_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

JSON_PATH = Path("src/common/devices.json")
EMBEDDING_MODEL = "text-embedding-3-small"


def clean_text(text: str | None) -> str:
    """
    Возвращает очищенную строку без NaN/None и лишних пробелов.
    """
    if not text:
        return ""
    value = str(text).strip()
    return value if value.lower() != "nan" else ""


def build_embedding_input(model: str, description: str) -> str:
    """
    Формирует компактный текст для эмбеддинга.
    """
    return f"Модель: {model}\nОписание: {description}"


async def get_embedding(text: str) -> list[float]:
    """
    Возвращает эмбеддинг текста фиксированной длины 1536.
    """
    r = await openai_client.embeddings.create(input=text, model=EMBEDDING_MODEL)
    return r.data[0].embedding


def unique_normalized_aliases(model: str, aliases: Iterable[str]) -> list[str]:
    """
    Возвращает список нормализованных алиасов без дублей, включая саму модель.
    """
    pool = [model] + list(aliases or [])
    seen: set[str] = set()
    out: list[str] = []
    for raw in pool:
        a = clean_text(raw)
        if not a:
            continue
        n = normalize(a)
        if not n or n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


async def upsert_aliases(session: AsyncSession, device_id: int, aliases: list[str]) -> None:
    """
    Идемпотентно добавляет алиасы устройства.
    """
    for a in aliases:
        exists = await session.execute(
            select(DeviceAlias.id).where(
                DeviceAlias.device_id == device_id,
                DeviceAlias.alias == a,
            )
        )
        if exists.scalar_one_or_none():
            continue
        session.add(DeviceAlias(device_id=device_id, alias=a))


async def import_devices() -> None:
    """
    Импорт моделей устройств из JSON с нормализацией алиасов и обновлением эмбеддингов.
    """
    logging.info("Начат импорт моделей устройств из JSON")
    with JSON_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    async with async_session_maker() as session:
        async with session.begin():
            for entry in data:
                model = clean_text(entry.get("model"))
                if not model:
                    logging.warning("Пропущена модель без названия")
                    continue

                description = clean_text(entry.get("description"))
                information = entry.get("information") or {}
                aliases = unique_normalized_aliases(model, entry.get("aliases") or [])

                q = await session.execute(select(Device).where(Device.model == model))
                existing = q.scalar_one_or_none()

                embedding = await get_embedding(build_embedding_input(model, description))

                if existing:
                    existing.description = description
                    existing.information = information
                    existing.embedding = embedding
                    device = existing
                    action = "Обновляется"
                else:
                    device = Device(
                        model=model,
                        description=description,
                        information=information,
                        embedding=embedding,
                    )
                    session.add(device)
                    await session.flush()
                    action = "Добавлена новая"

                await upsert_aliases(session, device.id, aliases)
                logging.info("%s модель: %s", action, model)

    logging.info("Импорт моделей завершён")


if __name__ == "__main__":
    asyncio.run(import_devices())
