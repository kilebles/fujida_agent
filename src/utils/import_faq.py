import csv
import asyncio
import logging

from pathlib import Path
from sqlalchemy import select

from db.session import async_session_maker
from db.models.faq_entry import FAQEntry
from common.openai_client import openai_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

CSV_PATH = Path("src/common/faq.csv")


def clean_text(text: str | None) -> str | None:
    if text is None:
        return None
    value = str(text).strip()
    return value if value and value.lower() != "nan" else None


def build_embedding_input(question: str, answer: str) -> str:
    return f"Вопрос: {question}\nОтвет: {answer}"


async def get_embedding(text: str) -> list[float]:
    response = await openai_client.embeddings.create(
        input=text,
        model="text-embedding-3-small",
    )
    return response.data[0].embedding


async def import_faq() -> None:
    logging.info("Начат импорт FAQ из CSV")
    async with async_session_maker() as session:
        with CSV_PATH.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            async with session.begin():
                for row in reader:
                    question = clean_text(row.get("question"))
                    answer = clean_text(row.get("answer"))
                    if not question or not answer:
                        logging.warning("Пропущена строка с неполными данными")
                        continue
                    result = await session.execute(
                        select(FAQEntry).where(FAQEntry.question == question)
                    )
                    existing = result.scalar_one_or_none()
                    input_text = build_embedding_input(question, answer)
                    embedding = await get_embedding(input_text)
                    if existing:
                        logging.info("Обновляется существующий вопрос: %s", question)
                        existing.answer = answer
                        existing.embedding = embedding
                    else:
                        logging.info("Добавлен новый вопрос: %s", question)
                        session.add(
                            FAQEntry(
                                question=question,
                                answer=answer,
                                embedding=embedding,
                            )
                        )
    logging.info("Импорт FAQ завершён")


if __name__ == "__main__":
    asyncio.run(import_faq())
