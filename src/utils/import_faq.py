import asyncio
import csv

from pathlib import Path
from sqlalchemy import select

from db.session import async_session_maker
from db.models.faq_entry import FAQEntry
from logger import get_logger, setup_logging
from common.openai_client import ensure_openai_client, close_openai_client

setup_logging()
logger = get_logger(__name__)

CSV_PATH = Path("src/common/faq.csv")
EMBEDDING_MODEL = "text-embedding-3-small"


def clean_text(text: str | None) -> str:
    """
    Возвращает очищенную строку без NaN/None и лишних пробелов.
    """
    if not text:
        return ""
    value = str(text).strip()
    return value if value.lower() != "nan" else ""


def build_embedding_input(question: str, answer: str) -> str:
    """
    Возвращает объединённый текст для эмбеддинга.
    """
    return f"Вопрос: {question}\nОтвет: {answer}"


async def get_embedding(text: str) -> list[float]:
    """
    Возвращает эмбеддинг текста фиксированной длины 1536.
    """
    client = await ensure_openai_client()
    resp = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text or "",
    )
    return resp.data[0].embedding


async def import_faq() -> None:
    """
    Импорт и апсерт записей FAQ из CSV с генерацией эмбеддингов.
    """
    logger.info("Начат импорт FAQ из CSV")
    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        async with async_session_maker() as session:
            async with session.begin():
                for row in reader:
                    question = clean_text(row.get("question"))
                    answer = clean_text(row.get("answer"))
                    if not question or not answer:
                        logger.warning("Пропущена строка с неполными данными", extra={"row": row})
                        continue

                    existing = (
                        await session.execute(
                            select(FAQEntry).where(FAQEntry.question == question)
                        )
                    ).scalar_one_or_none()

                    emb_input = build_embedding_input(question, answer)
                    embedding = await get_embedding(emb_input)

                    if existing:
                        existing.answer = answer
                        existing.embedding = embedding
                        action = "Обновляется"
                    else:
                        session.add(
                            FAQEntry(
                                question=question,
                                answer=answer,
                                embedding=embedding,
                            )
                        )
                        action = "Добавлен новый"

                    logger.info("%s вопрос: %s", action, question)

    logger.info("Импорт FAQ завершён")


async def main() -> None:
    """
    Запускает импорт и корректно закрывает HTTP-клиент.
    """
    try:
        await import_faq()
    finally:
        try:
            await close_openai_client()
        except RuntimeError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
