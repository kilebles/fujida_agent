from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from apps.knowledge_base.services.device_repo import DeviceRepo


BRAND_TOKENS = {"karma", "zoom"}
GENERIC_TOKENS = {"fujida"}
FAMILY_BASES: Dict[str, set[str]] = {
    "zoom": {"smart", "hit", "blik", "okko"},
    "karma": {"bliss", "pro", "one", "slim", "hara", "s", "duos", "blik", "hit"},
}
GENERIC_MODS = {"max", "duo", "ai", "wifi", "se"}
MOD_ORDER = ("s", "max", "se", "ai", "duo", "wifi")


@dataclass(frozen=True)
class DeviceIndex:
    """
    Индекс устройства: разложение названия на семью, базу и модификаторы.
    """

    device_id: int
    title: str
    family: str | None
    base: str | None
    mods: frozenset[str]
    tokens_all: frozenset[str]


@dataclass
class Decision:
    """
    Решение по одному запросу для интент-роутера.
    """

    query: str
    picked: str | None
    candidates: Tuple[str, ...]
    confidence: float
    accepted: bool
    reason: str


class StructuredAliasResolver:
    """
    Резолвер, собирающий кандидатов по семье/базе и модификаторам.

    Без модификаторов возвращает всю ветку линейки и выбирает модель
    с минимальным числом модификаторов. Если в запросе есть модификаторы,
    оставляет только модели, которые их покрывают.
    """

    def __init__(self) -> None:
        """
        Инициализирует пустые индексы.
        """
        self._by_id: Dict[int, DeviceIndex] = {}
        self._alias_to_ids: Dict[str, set[int]] = {}
        self._by_family: Dict[str, set[int]] = {}
        self._by_base: Dict[str, set[int]] = {}
        self._by_family_base: Dict[tuple[str, str], set[int]] = {}
        self._base_to_families: Dict[str, set[str]] = {}

    async def warmup(self, session: AsyncSession) -> None:
        """
        Прогревает индексы из БД и алиасов.
        """
        repo = DeviceRepo(session)
        id_pairs = await repo.list_device_titles()
        alias_pairs = await repo.list_alias_pairs()

        by_id: dict[int, DeviceIndex] = {}
        by_family: dict[str, set[int]] = {}
        by_base: dict[str, set[int]] = {}
        by_family_base: dict[tuple[str, str], set[int]] = {}
        base_to_families: dict[str, set[str]] = {}

        for device_id, title in id_pairs:
            family, base, mods, tokens = self._parse_title(title)
            idx = DeviceIndex(
                device_id=device_id,
                title=title,
                family=family,
                base=base,
                mods=frozenset(mods),
                tokens_all=frozenset(tokens),
            )
            by_id[device_id] = idx
            if family:
                by_family.setdefault(family, set()).add(device_id)
            if base:
                by_base.setdefault(base, set()).add(device_id)
            if family and base:
                by_family_base.setdefault((family, base), set()).add(device_id)
                base_to_families.setdefault(base, set()).add(family)

        alias_to_ids: dict[str, set[int]] = {}
        for device_id, title in id_pairs:
            di = by_id[device_id]
            for key in self._expansions_for_index(di):
                alias_to_ids.setdefault(key, set()).add(device_id)

        for alias, device_id in alias_pairs:
            k = self._norm_ascii(alias)
            if not k:
                continue
            alias_to_ids.setdefault(k, set()).add(int(device_id))

        self._by_id = by_id
        self._alias_to_ids = alias_to_ids
        self._by_family = by_family
        self._by_base = by_base
        self._by_family_base = by_family_base
        self._base_to_families = base_to_families

    async def resolve_for_router(
        self, raw_queries: Sequence[str], max_candidates: int = 12
    ) -> List[dict]:
        """
        Возвращает решения для интент-роутера.
        """
        out: List[dict] = []
        for q in raw_queries:
            d = await self.resolve_one(q, max_candidates=max_candidates)
            out.append(
                {
                    "query": q,
                    "picked": d.picked,
                    "candidates": list(d.candidates),
                    "confidence": d.confidence,
                    "accepted": d.accepted,
                    "reason": d.reason,
                }
            )
        return out

    async def resolve_one(
        self, query: str, max_candidates: int = 12
    ) -> Decision:
        """
        Возвращает кандидатов и лучший выбор под запрос.
        """
        key = self._norm_ascii(query)
        q_family, q_base, q_mods, _ = self._parse_tokens(key.split())

        cand_ids = set()
        if q_family and q_base:
            cand_ids |= set(self._by_family_base.get((q_family, q_base), set()))
        if q_base and not q_family:
            cand_ids |= set(self._by_base.get(q_base, set()))
        if q_family and not q_base:
            cand_ids |= set(self._by_family.get(q_family, set()))

        alias_hits = self._alias_to_ids.get(key, set())
        if alias_hits:
            cand_ids |= alias_hits

        cand_ids = self._filter_by_mods(cand_ids, q_mods)

        if not cand_ids:
            return Decision(
                query=query,
                picked=None,
                candidates=tuple(),
                confidence=0.0,
                accepted=False,
                reason="no_candidates",
            )

        ordered = self._order_for_query(cand_ids, q_mods)
        titles = self._ids_to_titles(ordered)
        picked = titles[0] if titles else None
        many = len(ordered) > 1
        conf = 1.0 if not many else 0.9
        accepted = not many
        reason = "preferred_min_mods" if many else "exact"
        return Decision(
            query=query,
            picked=picked,
            candidates=tuple(titles[:max_candidates]),
            confidence=conf,
            accepted=accepted,
            reason=reason,
        )

    def _filter_by_mods(self, ids: set[int], q_mods: set[str]) -> set[int]:
        """
        Фильтрует кандидатов по покрытию модификаторов.
        """
        if not ids:
            return set()
        if not q_mods:
            return ids
        keep: set[int] = set()
        for i in ids:
            di = self._by_id.get(i)
            if not di:
                continue
            if q_mods.issubset(di.mods):
                keep.add(i)
        return keep

    def _order_for_query(self, ids: set[int], q_mods: set[str]) -> List[int]:
        """
        Сортирует кандидатов по покрытию модификаторов.
        """
        def conflict_score(mods: frozenset[str]) -> int:
            has_conflict = ("s" in q_mods and "max" in mods) or ("max" in q_mods and "s" in mods)
            return 1 if has_conflict else 0

        def sort_key(device_id: int) -> tuple[int, int, int, int, int, int]:
            di = self._by_id[device_id]
            matched = len(di.mods & q_mods)
            missing = len(q_mods - di.mods)
            extra = len(di.mods - q_mods)
            conf = conflict_score(di.mods)
            tokens_len = len(self._norm_ascii(di.title).split())
            return (missing, conf, extra, -matched, tokens_len, device_id)

        return sorted(ids, key=sort_key)

    def _expansions_for_index(self, di: DeviceIndex) -> List[str]:
        """
        Генерирует алиасы для устройства по детерминированным префиксам модификаторов.
        """
        if not di.base:
            return []
        family = di.family
        base = di.base
        mods = sorted(di.mods, key=lambda m: MOD_ORDER.index(m) if m in MOD_ORDER else 999)

        with_brand: List[str] = []
        without_brand: List[str] = []

        if family:
            with_brand.append(f"{family} {base}")
        without_brand.append(base)

        if mods:
            for k in range(1, len(mods) + 1):
                seq = " ".join([base, *mods[:k]])
                without_brand.append(seq)
                if family:
                    with_brand.append(f"{family} {seq}")

        keys = with_brand + without_brand
        return [self._norm_ascii(k) for k in keys if k.strip()]

    def _parse_title(
        self, title: str
    ) -> tuple[str | None, str | None, set[str], set[str]]:
        """
        Разбирает название модели на семью, базу и модификаторы.
        """
        tokens = self._norm_ascii(title).split()
        return self._parse_tokens(tokens)

    def _parse_tokens(
        self, tokens: List[str]
    ) -> tuple[str | None, str | None, set[str], set[str]]:
        """
        Разбирает токены запроса на семью, базу и модификаторы.
        """
        toks = [t for t in tokens if t and t not in GENERIC_TOKENS]
        if not toks:
            return None, None, set(), set()

        family = toks[0] if toks[0] in BRAND_TOKENS else None
        rest = toks[1:] if family else toks[:]

        base: str | None = None
        mods: List[str] = []

        if family:
            allowed_bases = FAMILY_BASES.get(family, set())
            for t in rest:
                if t in allowed_bases:
                    base = t
                    break
            mod_set = self._mods_for_family(family)
            for t in rest:
                if base is None and t not in mod_set and t not in GENERIC_TOKENS:
                    base = t
                    continue
                if base is not None and t in mod_set:
                    mods.append(t)
        else:
            all_bases = set().union(*FAMILY_BASES.values())
            for t in rest:
                if t in all_bases:
                    base = t
                    break
            mod_set = self._mods_for_family(None)
            for t in rest:
                if base is None and t not in mod_set and t not in GENERIC_TOKENS:
                    base = t
                    continue
                if base is not None and t in mod_set:
                    mods.append(t)

        all_tokens = set(toks)
        return family, base, set(mods), all_tokens

    def _mods_for_family(self, family: str | None) -> set[str]:
        if family is None:
            return GENERIC_MODS | {"s"}
        return GENERIC_MODS | {"s"}

    def _ids_to_titles(self, ids: Iterable[int]) -> List[str]:
        """
        Преобразует id устройств в уникальные названия.
        """
        out: List[str] = []
        seen: set[str] = set()
        for i in ids:
            di = self._by_id.get(i)
            if not di:
                continue
            t = di.title
            if t in seen:
                continue
            out.append(t)
            seen.add(t)
        return out

    @staticmethod
    def _norm_ascii(s: str) -> str:
        s = s.lower().replace("ё", "e")
        s = re.sub(r"[^\w\s\-+]", " ", s, flags=re.UNICODE)
        s = re.sub(r"[\s\u00A0]+", " ", s).strip()
        if not s:
            return s
        syn = {
            "зум": "zoom",
            "карма": "karma",
            "хит": "hit",
            "блис": "bliss",
            "блисс": "bliss",
            "блик": "blik",
            "окко": "okko",
            "око": "okko",
            "смарт": "smart",
            "макс": "max",
            "про": "pro",
            "дуо": "duo",
            "вайфай": "wifi",
            "вай фай": "wifi",
            "вифи": "wifi",
            "ви-фи": "wifi",
            "эс": "s",
            "се": "se",
            "сэ": "se",
            "ван": "one",
            "уан": "one",
        }
        tokens = [syn.get(t, t) for t in s.split()]
        return " ".join(tokens)


_service: StructuredAliasResolver | None = None


def get_alias_search_cached() -> StructuredAliasResolver | None:
    """
    Возвращает прогретый резолвер, если он уже инициализирован.
    """
    return _service


async def get_alias_search(session: AsyncSession) -> StructuredAliasResolver:
    """
    Возвращает прогретый резолвер.
    """
    global _service
    if _service is None:
        _service = StructuredAliasResolver()
        await _service.warmup(session)
    return _service
