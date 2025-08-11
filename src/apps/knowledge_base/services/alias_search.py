import re
import ahocorasick

from typing import Iterable
from dataclasses import dataclass
from rapidfuzz import fuzz, process
from utils.text import normalize
from sqlalchemy.ext.asyncio import AsyncSession

from apps.knowledge_base.services.device_repo import DeviceRepo


GENERIC_TOKENS = {
    "fujida",
    "фуджида",
    "фудзида"
}

RU_EN_SYNONYMS = {
    "вайфай": "wifi",
    "вифи": "wifi",
    "ви-фи": "wifi",
    "макс": "max",
    "про": "pro",
    "дуо": "duo",
    "эс": "s",
    "с": "s",
    "се": "se",
    "сэ": "se",
    "смарт": "smart",
    "хит": "hit",
    "блик": "blik",
    "блис": "bliss",
    "блисс": "bliss",
    "зум": "zoom",
    "карма": "karma",
}

MODIFIER_TOKENS = {
    "max",
    "ai",
    "duo",
    "wifi",
    "s",
    "se",
}

STOP_TOKENS = {
    "что", "какой", "какая", "какие",
    "лучше", "лучший", "лучшее",
    "сравни", "сравнить", "расскажи", "скажи", "скажите",
}

BRAND_TOKENS = {"karma", "zoom"}

DISJUNCTION_RE = re.compile(
    r"\b(или|либо|vs\.?|против)\b|[\/\|,;]",
    flags=re.IGNORECASE,
)


@dataclass
class Match:
    alias: str
    start: int
    end: int


@dataclass
class DeviceIndex:
    all_tokens: set[str]
    base_tokens: set[str]
    mod_tokens: set[str]
    brand: str | None
    
    
@dataclass
class ChunkDecision:
    query: str
    brand: str | None
    q_mods: tuple[str, ...]
    candidates: tuple[str, ...]
    picked: str | None
    confidence: float
    accepted: bool
    reason: str
    

class AliasSearchService:
    """Поиск моделей с учётом расширенных алиасов, сравнения и специфичности."""

    def __init__(self) -> None:
        self._ac: ahocorasick.Automaton | None = None
        self._alias_to_ids: dict[str, set[int]] = {}
        self._id_to_model: dict[int, str] = {}
        self._device_index: dict[int, DeviceIndex] = {}

    async def warmup(self, session: AsyncSession) -> None:
        """Инициализирует автомат, словари и индексы из БД, добавляет алиас-расширения."""
        repo = DeviceRepo(session)
        alias_pairs = await repo.list_alias_pairs()
        id_pairs = await repo.list_device_titles()

        self._id_to_model = {i: m for i, m in id_pairs}
        self._device_index = self._build_device_index(id_pairs)

        ac = ahocorasick.Automaton()
        alias_to_ids: dict[str, set[int]] = {}

        for raw_alias, device_id in alias_pairs:
            a = self._norm(raw_alias)
            if not a:
                continue
            if a not in alias_to_ids:
                alias_to_ids[a] = set()
                ac.add_word(a, a)
            alias_to_ids[a].add(device_id)

        for device_id, title in id_pairs:
            title_n = self._norm(title)
            brand, base_core, mods = self._split_brand_core_mod(title_n.split())
            if not brand and not base_core:
                continue
            expansions = self._make_alias_expansions(brand, base_core, mods)
            for a in expansions:
                if a not in alias_to_ids:
                    alias_to_ids[a] = set()
                    ac.add_word(a, a)
                alias_to_ids[a].add(device_id)

        ac.make_automaton()
        self._ac = ac
        self._alias_to_ids = alias_to_ids

    def _build_device_index(
        self, id_pairs: Iterable[tuple[int, str]]
    ) -> dict[int, DeviceIndex]:
        idx: dict[int, DeviceIndex] = {}
        for i, title in id_pairs:
            t_norm = self._norm(title)
            tokens = [t for t in t_norm.split() if t]
            brand = None
            for t in tokens:
                if t in BRAND_TOKENS:
                    brand = t
                    break
            tokens_wo_generic = [t for t in tokens if t not in GENERIC_TOKENS]
            mods = {t for t in tokens_wo_generic if t in MODIFIER_TOKENS}
            base = {
                t
                for t in tokens_wo_generic
                if t not in mods and t not in BRAND_TOKENS
            }
            idx[i] = DeviceIndex(
                all_tokens=set(tokens_wo_generic),
                base_tokens=base,
                mod_tokens=mods,
                brand=brand,
            )
        return idx

    def _split_brand_core_mod(
        self, tokens: list[str]
    ) -> tuple[str | None, list[str], list[str]]:
        tokens = [t for t in tokens if t and t not in GENERIC_TOKENS]
        if not tokens:
            return None, [], []
        brand = tokens[0] if tokens[0] in BRAND_TOKENS else None
        core = tokens[1:] if brand else tokens
        base_core = core[:1] if core else []
        rest = core[1:] if core else []
        mods = [t for t in rest if t in MODIFIER_TOKENS]
        return brand, base_core, mods

    def _make_alias_expansions(
        self, brand: str | None, base_core: list[str], mods: list[str]
    ) -> set[str]:
        start = ([brand] if brand else []) + base_core
        if not start:
            return set()
        out: set[str] = set()
        out.add(" ".join(start))
        for k in range(1, len(mods) + 1):
            out.add(" ".join(start + mods[:k]))
        return out

    def _require_ready(self) -> None:
        if self._ac is None:
            raise RuntimeError("AliasSearchService is not initialized")

    def find_models(self, query: str, top_k: int = 10) -> list[str]:
        """Возвращает список моделей, учитывая сравнение, алиас-расширения и токеновый фолбэк."""
        self._require_ready()
        chunks = self._split_disjunction_raw(query)

        if len(chunks) > 1:
            picked: list[int] = []
            prev_brand: str | None = None
            for chunk in chunks:
                cn = self._norm(chunk)
                if not cn:
                    continue
                q_tokens = set(cn.split())
                brand = next(iter(q_tokens & BRAND_TOKENS), None) or prev_brand
                ids = self._rank_all(cn)
                ids = self._filter_by_brand(ids, brand)
                ids = self._rerank_by_specificity(cn, ids)
                ids = self._postfilter_by_mods(q_tokens & MODIFIER_TOKENS, ids)
                best = self._pick_best_for_chunk(cn, ids)
                if best is not None:
                    picked.append(best)
                prev_brand = brand
            return self._to_models(picked)

        qn = self._norm(query)
        q_tokens = set(qn.split())
        brand = next(iter(q_tokens & BRAND_TOKENS), None)
        ids = self._rank_all(qn)
        ids = self._filter_by_brand(ids, brand)
        ids = self._rerank_by_specificity(qn, ids)
        ids = self._postfilter_by_mods(q_tokens & MODIFIER_TOKENS, ids)
        ids = self._trim_extras(qn, ids, top_k)
        return self._to_models(ids)

    def _rank_all(self, qn: str) -> list[int]:
        ids_aho = self._rank_aho(qn)
        if ids_aho:
            return ids_aho

        ids_fuzzy = self._rank_fuzzy(qn)
        ids_tok = self._candidates_by_tokens(qn)

        if not ids_fuzzy and not ids_tok:
            return []

        seen: set[int] = set()
        one_word = len(qn.split()) == 1

        merged: list[int] = []
        primary = ids_tok if one_word else ids_fuzzy
        secondary = ids_fuzzy if one_word else ids_tok

        for i in primary:
            if i not in seen:
                merged.append(i)
                seen.add(i)
        for i in secondary:
            if i not in seen:
                merged.append(i)
                seen.add(i)

        return merged


    def _rank_aho(self, qn: str) -> list[int]:
        matches: list[Match] = []
        for end, alias in self._ac.iter(qn):  # type: ignore[union-attr]
            start = end - len(alias) + 1
            matches.append(Match(alias=alias, start=start, end=end))

        if not matches:
            return []

        by_device: dict[int, float] = {}
        covered_positions: dict[int, set[int]] = {}

        for m in matches:
            alias_tokens = m.alias.split()
            token_count = len(alias_tokens)
            alias_len = len(m.alias)
            is_generic = token_count == 1 and alias_tokens[0] in GENERIC_TOKENS
            base_score = 10.0 * token_count + 0.1 * alias_len
            if is_generic:
                base_score -= 3.0
            for device_id in self._alias_to_ids.get(m.alias, set()):
                by_device[device_id] = by_device.get(device_id, 0.0) + base_score
                pos = covered_positions.setdefault(device_id, set())
                pos.update(range(m.start, m.end + 1))

        for device_id, pos in covered_positions.items():
            by_device[device_id] = by_device.get(device_id, 0.0) + 0.05 * float(
                len(pos)
            )

        ranked = sorted(by_device.items(), key=lambda x: (-x[1], x[0]))
        return [i for i, _ in ranked]

    def _rank_fuzzy(self, qn: str, threshold: int = 82, limit: int = 30) -> list[int]:
        if not self._alias_to_ids:
            return []

        choices: Iterable[str] = self._alias_to_ids.keys()

        tok_cnt = len(qn.split())
        dyn_threshold = 90 if tok_cnt == 1 else threshold

        cand = list(process.extract(qn, choices, scorer=fuzz.WRatio, limit=limit))
        tokens = qn.split()
        bigrams = [" ".join(tokens[i : i + 2]) for i in range(len(tokens) - 1)]
        if bigrams:
            cand += list(
                process.extract(
                    bigrams, choices, scorer=fuzz.WRatio, limit=max(10, len(bigrams))
                )
            )

        scores: dict[int, float] = {}
        for alias, score, _ in cand:
            if score < dyn_threshold:
                continue
            token_count = len(alias.split())
            alias_len = len(alias)
            bonus = 0.03 * alias_len + 1.5 * (token_count - 1)
            for device_id in self._alias_to_ids.get(alias, set()):
                scores[device_id] = max(
                    scores.get(device_id, 0.0), float(score) + bonus
                )

        ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        return [i for i, _ in ranked]

    def _candidates_by_tokens(self, qn: str, limit: int = 50) -> list[int]:
        q = set(qn.split()) - GENERIC_TOKENS - BRAND_TOKENS
        if not q:
            return []
        scored: list[tuple[int, float]] = []
        for i, di in self._device_index.items():
            base_hit = len(di.base_tokens & q)
            if base_hit == 0:
                continue
            mod_shared = len(di.mod_tokens & q)
            mod_missing = len((q & MODIFIER_TOKENS) - di.mod_tokens)
            score = 3.0 * float(base_hit) + 2.0 * float(mod_shared) - 2.5 * float(
                mod_missing
            )
            scored.append((i, score))
        scored.sort(key=lambda x: (-x[1], x[0]))
        return [i for i, _ in scored[:limit]]

    def _rerank_by_specificity(self, qn: str, ids: list[int]) -> list[int]:
        if not ids:
            return []

        q_tokens = set(self._norm(qn).split())
        q_mods = q_tokens & MODIFIER_TOKENS

        scored: list[tuple[int, float]] = []
        for i in ids:
            di = self._device_index.get(i)
            if not di:
                continue

            base_total = len(di.base_tokens) or 1
            base_hit = len(di.base_tokens & q_tokens)
            base_cover = base_hit / base_total

            shared_mods = len(di.mod_tokens & q_mods)
            missing_mods = len(q_mods - di.mod_tokens)
            extra_mods = len(di.mod_tokens - q_mods)
            mod_cover = shared_mods / (len(q_mods) or 1)

            score = 40.0 * base_cover + 60.0 * mod_cover
            score -= 25.0 * float(missing_mods)
            score -= 3.0 * float(extra_mods)

            scored.append((i, score))

        scored.sort(key=lambda x: (-x[1], x[0]))
        return [i for i, _ in scored]

    def _split_disjunction_raw(self, s: str) -> list[str]:
        """
        Делит исходный текст на части до нормализации, чтобы запятая и прочая пунктуация
        не терялись и не склеивали перечисления в один кусок.
        """
        parts = [p.strip() for p in DISJUNCTION_RE.split(s) if p]
        out: list[str] = []
        for p in parts:
            if DISJUNCTION_RE.match(p):
                continue
            if p:
                out.append(p)
        return out
    

    def _pick_best_for_chunk(self, chunk: str, ids: list[int]) -> int | None:
        return ids[0] if ids else None

    def _trim_extras(self, qn: str, ids: list[int], top_k: int) -> list[int]:
        if not ids:
            return []

        q_tokens = set(self._norm(qn).split())
        q_mods = q_tokens & MODIFIER_TOKENS
        base_like = q_tokens - BRAND_TOKENS - MODIFIER_TOKENS
        brand_only = (q_tokens & BRAND_TOKENS) and not base_like and not q_mods

        if base_like or q_mods or brand_only:
            return ids[:1]

        return ids[:max(1, min(top_k, 2))]

    def _norm(self, s: str) -> str:
        base = normalize(s)
        tokens = base.split()
        out: list[str] = []
        for t in tokens:
            t = t.rstrip("?.!,;:…»›>)]}\"'`")
            if not t:
                continue
            out.append(RU_EN_SYNONYMS.get(t, t))
        return " ".join(out)

    def _to_models(self, ids: list[int]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for i in ids:
            m = self._id_to_model.get(i)
            if not m or m in seen:
                continue
            seen.add(m)
            out.append(m)
        return out

    def _postfilter_by_mods(self, q_mods: set[str], ids: list[int]) -> list[int]:
        if not ids or not q_mods:
            return ids
        stats: list[tuple[int, int, int]] = []
        for i in ids:
            di = self._device_index.get(i)
            if not di:
                continue
            missing = len(q_mods - di.mod_tokens)
            extra = len(di.mod_tokens - q_mods)
            stats.append((i, missing, extra))
        exact = [(i, extra) for i, missing, extra in stats if missing == 0]
        if not exact:
            return ids
        min_extra = min(extra for _, extra in exact)
        keep = {i for i, extra in exact if extra == min_extra}
        return [i for i in ids if i in keep]

    def _filter_by_brand(self, ids: list[int], brand: str | None) -> list[int]:
        if not brand:
            return ids
        filtered = [
            i
            for i in ids
            if (self._device_index.get(i) and self._device_index[i].brand == brand)
        ]
        return filtered or ids
    
    def find_models_detailed(self, query: str, top_k: int = 10) -> tuple[list[str], list[ChunkDecision]]:
        """Возвращает модели и решения по каждому куску с оценкой уверенности."""
        self._require_ready()
        chunks = self._split_disjunction_raw(query)

        if len(chunks) > 1:
            picked_ids: list[int] = []
            decisions: list[ChunkDecision] = []
            prev_brand: str | None = None
            for chunk in chunks:
                cn = self._norm(chunk)
                if not cn:
                    continue
                q_tokens = set(cn.split())
                brand = next(iter(q_tokens & BRAND_TOKENS), None) or prev_brand
                ids = self._rank_all(cn)
                ids = self._filter_by_brand(ids, brand)
                ids = self._rerank_by_specificity(cn, ids)
                ids = self._postfilter_by_mods(q_tokens & MODIFIER_TOKENS, ids)
                model_names = [self._id_to_model.get(i, "") for i in ids]
                best = ids[0] if ids else None
                if best is not None:
                    picked_ids.append(best)
                conf, ok, reason = self._confidence_for_chunk(
                    chunk=cn,
                    brand=brand,
                    ids=ids,
                    q_tokens=set(cn.split()),
                )
                decisions.append(
                    ChunkDecision(
                        query=cn,
                        brand=brand,
                        q_mods=tuple(sorted(q_tokens & MODIFIER_TOKENS)),
                        candidates=tuple(model_names[:5]),
                        picked=self._id_to_model.get(best) if best is not None else None,
                        confidence=conf,
                        accepted=ok,
                        reason=reason,
                    )
                )
                prev_brand = brand
            return self._to_models(picked_ids), decisions

        qn = self._norm(query)
        q_tokens = set(qn.split())
        brand = next(iter(q_tokens & BRAND_TOKENS), None)
        ids = self._rank_all(qn)
        ids = self._filter_by_brand(ids, brand)
        ids = self._rerank_by_specificity(qn, ids)
        ids = self._postfilter_by_mods(q_tokens & MODIFIER_TOKENS, ids)
        names = [self._id_to_model.get(i, "") for i in ids]
        conf, ok, reason = self._confidence_for_chunk(
            chunk=qn, brand=brand, ids=ids, q_tokens=q_tokens
        )
        decisions = [
            ChunkDecision(
                query=qn,
                brand=brand,
                q_mods=tuple(sorted(q_tokens & MODIFIER_TOKENS)),
                candidates=tuple(names[:5]),
                picked=self._id_to_model.get(ids[0]) if ids else None,
                confidence=conf,
                accepted=ok,
                reason=reason,
            )
        ]
        ids = self._trim_extras(qn, ids, top_k)
        return self._to_models(ids), decisions

    def _confidence_for_chunk(self, chunk: str, brand: str | None, ids: list[int], q_tokens: set[str]) -> tuple[float, bool, str]:
        if not ids:
            return 0.0, False, "no_candidates"

        di0 = self._device_index.get(ids[0])
        if not di0:
            return 0.0, False, "no_index"

        q_mods = q_tokens & MODIFIER_TOKENS
        base_like = q_tokens - BRAND_TOKENS - MODIFIER_TOKENS
        brand_present = bool(q_tokens & BRAND_TOKENS)
        brand_ok = (di0.brand == brand) or (brand is None)

        base_total = len(di0.base_tokens) or 1
        base_hit = len(di0.base_tokens & q_tokens)
        base_cover = base_hit / base_total

        missing_mods = len(q_mods - di0.mod_tokens)
        extra_mods = len(di0.mod_tokens - q_mods)
        many = len(ids) >= 6

        brand_only = brand_present and not base_like and not q_mods
        mods_only = not brand_present and not base_like and bool(q_mods)

        if brand_only and brand_ok:
            return 0.95, True, "brand_only"

        if mods_only and missing_mods == 0:
            return 0.90, True, "mods_only"

        if not brand_ok:
            score = 0.35 * (1.0 if missing_mods == 0 else 0.0)
            return max(0.0, min(1.0, score)), False, "brand_mismatch"

        score = 0.55 * base_cover
        score += 0.35 * (1.0 if missing_mods == 0 else 0.0)
        score += 0.10 * (0.5 if extra_mods <= 1 else 0.0)
        if many:
            score -= 0.10

        score = max(0.0, min(1.0, score))

        if q_mods and missing_mods > 0:
            return score, False, "mods_missing"
        if base_like and base_cover < 0.5:
            return score, False, "base_low_cover"
        if many and score < 0.7:
            return score, False, "too_many_candidates"

        return score, True, "ok"


_service: AliasSearchService | None = None


async def get_alias_search(session: AsyncSession) -> AliasSearchService:
    """Возвращает прогретый сервис поиска."""
    global _service
    if _service is None:
        _service = AliasSearchService()
        await _service.warmup(session)
    return _service
