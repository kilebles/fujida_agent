from __future__ import annotations

from typing import Iterable, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from apps.knowledge_base.services.device_repo import DeviceRepo
from common.openai_client import openai_client


_EMBEDDING_MODEL = "text-embedding-3-small"
_specs_search_cached: "SpecsSearch | None" = None


class SpecsSearch:
    """
    Поиск моделей по семантике описаний устройств с фильтрацией по характеристикам.
    """

    def __init__(self, repo: DeviceRepo) -> None:
        self._repo = repo

    async def _embed(self, text: str) -> list[float]:
        """
        Возвращает эмбеддинг для текста.
        """
        r = await openai_client.embeddings.create(input=text, model=_EMBEDDING_MODEL)
        return r.data[0].embedding

    async def search(
        self,
        features: Iterable[str],
        top_k: int = 50,
        max_distance: float | None = 0.28,
    ) -> List[Tuple[str, str, float]]:
        """
        Возвращает список кортежей (model, description, distance) по заданным признакам.
        """
        parts = [str(f).strip() for f in features if str(f or "").strip()]
        if not parts:
            return []

        query = " ".join(parts)
        emb = await self._embed(query)

        rows = await self._repo.vector_search_by_description(
            embedding=emb,
            features=parts,
            top_k=top_k,
            max_distance=max_distance,
        )

        if not rows:
            rows = await self._repo.vector_search_by_description(
                embedding=emb,
                features=parts,
                top_k=top_k,
                max_distance=None,
            )

        return rows


async def get_specs_search(session: AsyncSession) -> SpecsSearch:
    repo = DeviceRepo(session)
    return SpecsSearch(repo)


def get_specs_search_cached() -> SpecsSearch | None:
    return _specs_search_cached


def set_specs_search_cached(svc: SpecsSearch | None) -> None:
    global _specs_search_cached
    _specs_search_cached = svc
