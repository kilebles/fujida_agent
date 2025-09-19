from __future__ import annotations

import re
from typing import Any, Dict, List

from sqlalchemy import select, func, cast
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from db.models.devices import Device
from common.openai_client import ensure_openai_client

_EMBEDDING_MODEL = "text-embedding-3-large"
_specs_search_cached: SpecsSearch | None = None


def normalize_text(text: str) -> str:
    """
    Нормализует ввод пользователя и алиасы для поиска:
    - переводит в нижний регистр,
    - заменяет дефисы/подчёркивания на пробелы,
    - удаляет лишние пробелы.
    """
    text = text.lower()
    text = re.sub(r"[-_]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class SpecsSearch:
    """
    Семантический поиск по устройствам Fujida с выдачей топ-N моделей.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _embed(self, text: str) -> list[float]:
        """
        Возвращает эмбеддинг нормализованного текста фиксированной длины 3072.
        """
        client = await ensure_openai_client()
        norm_text = normalize_text(text or "")
        resp = await client.embeddings.create(
            model=_EMBEDDING_MODEL,
            input=norm_text,
        )
        return resp.data[0].embedding

    async def _search_similar(self, embedding: list[float], top_n: int) -> List[Device]:
        """
        Возвращает топ-N устройств по косинусной близости.
        """
        stmt = (
            select(Device)
            .order_by(func.cosine_distance(Device.vector, cast(embedding, Vector)))
            .limit(top_n)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def top_devices_json(self, user_message: str, *, top_n: int = 15) -> Dict[str, Any]:
        """
        Возвращает JSON с топ-N подходящими устройствами.
        """
        emb = await self._embed(user_message)
        rows = await self._search_similar(emb, top_n)
        return {
            "models": [r.model for r in rows],
            "descriptions": [r.vector_text for r in rows],
            "aliases": [[normalize_text(a) for a in (r.aliases or [])] for r in rows],
        }


async def get_specs_search(session: AsyncSession) -> SpecsSearch:
    """
    Создаёт сервис SpecsSearch на сессии БД.
    """
    return SpecsSearch(session)


def get_specs_search_cached() -> SpecsSearch | None:
    """
    Возвращает кешированный инстанс SpecsSearch.
    """
    return _specs_search_cached


def set_specs_search_cached(svc: SpecsSearch | None) -> None:
    """
    Кладёт сервис SpecsSearch в кеш.
    """
    global _specs_search_cached
    _specs_search_cached = svc