from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select, func, cast
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from db.models.faq_entry import FAQEntry
from common.openai_client import ensure_openai_client

_EMBEDDING_MODEL = "text-embedding-3-small"
_faq_search_cached: FAQSearch | None = None


class FAQSearch:
    """
    Семантический поиск по FAQ с выдачей топ-N вопросов и ответов.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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

    async def _search_similar(self, embedding: list[float], top_n: int) -> List[FAQEntry]:
        """
        Возвращает топ-N FAQ по косинусной близости.
        """
        stmt = (
            select(FAQEntry)
            .order_by(func.cosine_distance(FAQEntry.embedding, cast(embedding, Vector)))
            .limit(top_n)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def top_faq_json(self, user_message: str, *, top_n: int = 3) -> Dict[str, Any]:
        """
        Возвращает JSON с топ-N похожими вопросами и ответами.
        """
        emb = await self._embed(user_message)
        rows = await self._search_similar(emb, top_n)
        return {
            "top_questions": [r.question for r in rows],
            "top_answers": [r.answer for r in rows],
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
