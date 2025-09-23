from __future__ import annotations

from typing import Any, Dict, List, Tuple

from sqlalchemy import select, func, cast
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from db.models.faq_entry import FAQEntry
from common.openai_client import ensure_openai_client

_EMBEDDING_MODEL = "text-embedding-3-small"
_faq_search_cached: FAQSearch | None = None


class FAQSearch:
    """
    Семантический поиск по FAQ с приоритетом на точное совпадение.
    Если близость > threshold → возвращается только один результат,
    иначе — топ-N похожих.
    """

    def __init__(self, session: AsyncSession, threshold: float = 0.9) -> None:
        self._session = session
        self._threshold = threshold

    async def _embed(self, text: str) -> list[float]:
        """
        Возвращает эмбеддинг текста фиксированной длины 1536.
        """
        client = await ensure_openai_client()
        resp = await client.embeddings.create(
            model=_EMBEDDING_MODEL,
            input=text or "",
        )
        return resp.data[0].embedding

    async def _search_similar(
        self, embedding: list[float], top_n: int
    ) -> List[Tuple[FAQEntry, float]]:
        """
        Возвращает топ-N FAQ + их similarity score.
        """
        stmt = (
            select(
                FAQEntry,
                1 - func.cosine_distance(FAQEntry.embedding, cast(embedding, Vector)).label("score"),
            )
            .order_by(func.cosine_distance(FAQEntry.embedding, cast(embedding, Vector)))
            .limit(top_n)
        )
        result = await self._session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def top_faq_json(self, user_message: str, *, top_n: int = 3) -> Dict[str, Any]:
        """
        Возвращает JSON: если есть очень близкий матч — только его,
        иначе — топ-N похожих вопросов и ответов.
        """
        emb = await self._embed(user_message)
        rows = await self._search_similar(emb, top_n)

        if rows and rows[0][1] >= self._threshold:
            top = rows[0][0]
            return {
                "exact_match": {
                    "question": top.question,
                    "answer": top.answer,
                }
            }

        return {
            "top_questions": [r[0].question for r in rows],
            "top_answers": [r[0].answer for r in rows],
        }


async def get_faq_search(session: AsyncSession) -> FAQSearch:
    """
    Создаёт сервис FAQSearch на сессии БД.
    """
    return FAQSearch(session)


def get_faq_search_cached() -> FAQSearch | None:
    """
    Возвращает кешированный инстанс FAQSearch.
    """
    return _faq_search_cached


def set_faq_search_cached(svc: FAQSearch | None) -> None:
    """
    Кладёт сервис FAQSearch в кеш.
    """
    global _faq_search_cached
    _faq_search_cached = svc