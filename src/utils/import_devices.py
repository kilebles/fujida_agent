import asyncio
import json

from pathlib import Path
from sqlalchemy import select

from db.models.devices import Device
from db.session import async_session_maker
from logger import get_logger, setup_logging
from common.openai_client import ensure_openai_client, close_openai_client

setup_logging()
logger = get_logger(__name__)

JSON_PATH = Path("src/common/product.json")
EMBEDDING_MODEL = "text-embedding-3-large"


async def get_embedding(text: str) -> list[float]:
    client = await ensure_openai_client()
    resp = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text or "",
    )
    return resp.data[0].embedding


async def import_devices() -> None:
    logger.info("Начат импорт моделей устройств из JSON")
    with JSON_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    async with async_session_maker() as session:
        async with session.begin():
            for entry in data:
                model = entry.get("id")
                base_text = entry.get("vector_text") or ""
                aliases = entry.get("aliases") or []

                if not model or not base_text:
                    logger.warning(
                        "Пропущена запись без модели или текста",
                        extra={"entry": entry},
                    )
                    continue

                embedding_text = base_text
                if aliases:
                    embedding_text += "\n" + ", ".join(aliases)

                vec = await get_embedding(embedding_text)

                q = await session.execute(select(Device).where(Device.model == model))
                existing = q.scalar_one_or_none()

                if existing:
                    existing.vector_text = base_text
                    existing.vector = vec
                    existing.aliases = aliases
                    action = "Обновляется"
                else:
                    device = Device(
                        model=model,
                        vector_text=base_text,
                        vector=vec,
                        aliases=aliases,
                    )
                    session.add(device)
                    action = "Добавлена новая"

                logger.info("%s модель: %s", action, model)

    logger.info("Импорт моделей завершён")


async def main() -> None:
    try:
        await import_devices()
    finally:
        try:
            await close_openai_client()
        except RuntimeError:
            pass


if __name__ == "__main__":
    asyncio.run(main())