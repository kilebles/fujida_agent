from dataclasses import dataclass
from typing import Awaitable, Callable, Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from apps.knowledge_base.services.alias_search import (
    AliasSearchService,
    ChunkDecision,
)


@dataclass
class SearchResult:
    models: list[str]
    decisions: list[ChunkDecision]
    used_vector: bool


AsyncVectorFn = Callable[[str, int], Awaitable[Iterable[str]]]


class SearchGateway:
    """Маршрутизатор поиска: alias -> vector с порогами уверенности."""

    def __init__(self, alias_service: AliasSearchService, session: AsyncSession) -> None:
        self.alias = alias_service
        self.session = session
        self.low_conf = 0.80
        self.max_chunks_for_alias = 2

    async def search(
        self,
        query: str,
        vector_fn: AsyncVectorFn | None = None,
        top_k: int = 10,
    ) -> SearchResult:
        alias_models, decisions = self.alias.find_models_detailed(query, top_k=top_k)

        need_vector = self._need_vector(decisions)

        if not need_vector or vector_fn is None:
            return SearchResult(models=alias_models, decisions=decisions, used_vector=False)

        vector_models = list(await vector_fn(query, top_k))
        merged = self._merge_preferring_alias(decisions, alias_models, vector_models, top_k)
        return SearchResult(models=merged, decisions=decisions, used_vector=True)

    def _need_vector(self, decisions: list[ChunkDecision]) -> bool:
        if not decisions:
            return True

        accepted = [d for d in decisions if d.picked]
        strong = [d for d in accepted if d.accepted and d.confidence >= self.low_conf]

        if len(decisions) == 1 and strong:
            return False

        if len(strong) == len(decisions) and 1 <= len(strong) <= self.max_chunks_for_alias:
            return False

        if len(accepted) >= 3:
            return True

        if len(decisions) > self.max_chunks_for_alias:
            return True

        if any((not d.accepted) or (d.confidence < self.low_conf) for d in decisions):
            return True

        return False

    def _merge_preferring_alias(
        self,
        decisions: list[ChunkDecision],
        alias_models: list[str],
        vector_models: list[str],
        top_k: int,
    ) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()

        for d in decisions:
            if d.picked and d.accepted and d.confidence >= self.low_conf and d.picked not in seen:
                out.append(d.picked)
                seen.add(d.picked)

        for m in alias_models:
            if len(out) >= top_k:
                break
            if m and m not in seen:
                out.append(m)
                seen.add(m)

        for m in vector_models:
            if len(out) >= top_k:
                break
            if m and m not in seen:
                out.append(m)
                seen.add(m)

        return out
