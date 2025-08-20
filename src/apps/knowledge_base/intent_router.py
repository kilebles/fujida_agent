import json
import re
import time
from typing import Any, Dict, List

import common.openai_client as oai
from db.session import async_session_maker
from apps.knowledge_base.services.alias_search import (
    get_alias_search,
    get_alias_search_cached,
)
from apps.knowledge_base.services.specs_search import (
    get_specs_search,
    get_specs_search_cached,
    set_specs_search_cached,
)
from apps.knowledge_base.services.faq_search import (
    get_faq_search,
    get_faq_search_cached,
    set_faq_search_cached,
)
from apps.knowledge_base.services.device_repo import DeviceRepo

PROMPT = (
    "Ты маршрутизатор запросов о продуктах Fujida."
    "Всегда отвечай строго JSON."
    "Ключи: route ∈ {by_name, by_specs, by_faq}, user_query, models, features."
    "models — список ПОЛНЫХ имён моделей (без бренда «fujida», латиницей, в нижнем регистре)."
    "features — список характеристик или функций (на русском или английском),"
    "актуально только для route = \"by_specs\". Если в запросе встречаются характеристики,"
    "сохраняй их в естественном виде: «у каких моделей есть глонасс» остаётся «глонасс», «модели с задней камерой» остаётся «задняя камера»."
    "Технические термины типа «wifi», «128gb microsd» можно оставить латиницей."
    "Разделяй разные модели только если в запросе явно есть разделители: запятая, «или»,"
    "«либо», «vs», «против», «/», «|»."
    "Допустимые модификаторы моделей: max, pro, duo, ai, wifi, s, se, smart, hit, blik, bliss."
    "Исправляй ошибки в модификаторах: луо→duo, крмв→karma."
    "Кириллицу транслитерируй только в названиях моделей: зум→zoom, карма→karma, хит→hit, блисс/блис→bliss, блик→blik,"
    "Старайся не терять 'с', когда она относится к модели: хит с→hit s"
    "смарт→smart, макс→max, про→pro, дуо→duо, вайфай/вифи/ви-фи→wifi, эс/с→s, се/сэ→se, око/окко→okko"
    "Примеры классификации:"
    "  route = \"by_name\" — сравнение или выбор между конкретными моделями, а также запросы об описании или характеристиках конкретной модели:"
    "    «зум хит с луо» → models = [\"zoom hit s duo\"], features = []."
    "    «хит с дуо» → models = [\"hit s duo\"], features = []."
    "    «карма про и блисс сравни» → models = [\"karma pro\", \"bliss\"], features = []."
    "    «расскажи про карму про макс» → models = [\"karma pro max\"], features = []."
    "  route = \"by_specs\" — запросы по характеристикам или поиску моделей с нужным функционалом:"
    "    «у каких моделей есть глонасс» → models = [], features = [\"глонасс\"]."
    "    «лучшая модель с радар-детектором и с картой памяти 128 гб» → models = [], features = [\"радар-детектор\", \"карта памяти 128 гб\"]."
    "  route = \"by_faq\" — запросы про эксплуатацию, проблемы, инструкции, аксессуары, совместимость, обновления, ремонт или неисправности:"
    "    «какие sd-карты совместимы с устройствами karma» → models = [], features = []."
    "    «камеру проехал, а комбо всё ещё оповещает по радиомодулю» → models = [], features = []."
    "Если запрос подходит к нескольким категориям, выбирай ту, которая соответствует главной цели пользователя."
)

_ALLOWED_ROUTES = {"by_name", "by_specs", "by_faq"}
_LLM_CACHE_TTL = 60.0
_LLM_CACHE_MAX = 512
MAX_ALIAS_CANDIDATES = 12
SPECS_TOP_K = 50
SPECS_MAX_DISTANCE = 0.6


def _split_disjunctions(text: str) -> List[str]:
    pat = re.compile(
        r"\b(от|и|или|либо|vs\.?|против)\b|[\/\|,;]",
        flags=re.IGNORECASE,
    )
    parts = [p.strip() for p in pat.split(text) if p]
    out: List[str] = []
    for p in parts:
        if pat.match(p):
            continue
        if p:
            out.append(p)
    return out


def _norm_ascii_ru2en(s: str) -> str:
    s = s.lower().replace("ё", "e")
    s = re.sub(r"[^\w\s\-+]", " ", s, flags=re.UNICODE)
    s = re.sub(r"[\s\u00A0]+", " ", s).strip()
    syn = {
        "зум": "zoom",
        "карма": "karma",
        "хит": "hit",
        "блис": "bliss",
        "блисс": "bliss",
        "блик": "blik",
        "смарт": "smart",
        "макс": "max",
        "про": "pro",
        "дуо": "duo",
        "вайфай": "wifi",
        "вифи": "wifi",
        "ви-фи": "wifi",
        "эс": "s",
        "с": "s",
        "се": "se",
        "сэ": "se",
    }
    tokens = [syn.get(t, t) for t in s.split()]
    return " ".join(tokens)


_llm_cache: dict[str, tuple[float, Dict[str, Any]]] = {}


def _cache_get(key: str) -> Dict[str, Any] | None:
    now = time.time()
    rec = _llm_cache.get(key)
    if not rec:
        return None
    ts, value = rec
    if now - ts > _LLM_CACHE_TTL:
        _llm_cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: Dict[str, Any]) -> None:
    if len(_llm_cache) >= _LLM_CACHE_MAX:
        _llm_cache.pop(next(iter(_llm_cache)))
    _llm_cache[key] = (time.time(), value)


def _normalize_llm_output(parsed: Dict[str, Any], user_query: str) -> Dict[str, Any]:
    route = str(parsed.get("route") or "").strip().lower()
    models_raw = parsed.get("models") or []
    if route not in _ALLOWED_ROUTES:
        route = "by_name" if models_raw else "by_faq"

    models: List[str] = []
    for m in models_raw:
        s = str(m or "").strip().lower()
        s = s.replace("ё", "e")
        s = " ".join(s.split())
        if s:
            models.append(s)

    chunks = [_norm_ascii_ru2en(c) for c in _split_disjunctions(user_query)]
    if chunks and len(models) > len(chunks):
        merged: List[str] = []
        model_tokens: List[str] = []
        for m in models:
            model_tokens.extend(m.split())
        pos = 0
        for ch in chunks:
            want = len(ch.split())
            if want <= 0:
                continue
            piece = " ".join(model_tokens[pos : pos + want]).strip()
            if piece:
                merged.append(piece)
            pos += want
        if len(merged) == len(chunks):
            models = merged

    parsed["route"] = route
    parsed["user_query"] = parsed.get("user_query") or user_query
    parsed["models"] = models
    parsed["features"] = parsed.get("features") or []
    return parsed


async def _route_with_llm(user_query: str) -> Dict[str, Any]:
    cached = _cache_get(user_query)
    if cached is not None:
        return cached

    client = await oai.ensure_openai_client()
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=160,
        seed=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": user_query},
        ],
    )
    try:
        raw = json.loads(resp.choices[0].message.content)
    except Exception:
        raw = {"route": "by_faq", "user_query": user_query, "models": [], "features": []}

    parsed = _normalize_llm_output(raw, user_query)
    _cache_set(user_query, parsed)
    return parsed


async def route_intent_llm(user_query: str) -> Dict[str, Any]:
    base_json = await _route_with_llm(user_query)
    route = base_json.get("route")
    models = base_json.get("models", []) or []
    features = base_json.get("features", []) or []

    if route == "by_faq":
        svc = get_faq_search_cached()
        if svc is None:
            async with async_session_maker() as session:
                svc = await get_faq_search(session)
                set_faq_search_cached(svc)
        faq = await svc.top_faq_json(user_query, top_n=3)
        base_json["found_models"] = []
        base_json["information_diff"] = {}
        base_json["top_questions"] = faq["top_questions"]
        base_json["top_answers"] = faq["top_answers"]
        return base_json

    if route == "by_specs" and features:
        svc = get_specs_search_cached()
        if svc is None:
            async with async_session_maker() as session:
                svc = await get_specs_search(session)
                set_specs_search_cached(svc)
        rows = await svc.search(
            features=features,
            top_k=SPECS_TOP_K,
            max_distance=SPECS_MAX_DISTANCE,
        )
        base_json["found_models"] = [{"model": m, "description": d} for m, d, _ in rows]
        base_json["information_diff"] = {}
        return base_json

    if route == "by_specs" and not features:
        base_json["found_models"] = []
        base_json["information_diff"] = {}
        return base_json

    svc = get_alias_search_cached()
    if svc is None:
        async with async_session_maker() as session:
            svc = await get_alias_search(session)

    decisions = await svc.resolve_for_router(models, max_candidates=MAX_ALIAS_CANDIDATES)

    picked: List[str] = []
    for d in decisions:
        p = d.get("picked")
        if isinstance(p, str) and p:
            picked.append(p)

    info_map: Dict[str, dict] = {}
    if picked:
        async with async_session_maker() as session:
            repo = DeviceRepo(session)
            info_map = await repo.get_information_by_models(picked)

    found_models: List[Dict[str, Any]] = []
    for d in decisions:
        p = d.get("picked")
        found_models.append(
            {
                "model": p,
                "information": info_map.get(p, {}) if len(picked) == 1 else {},
                "candidates": d.get("candidates", []),
            }
        )
    base_json["found_models"] = found_models

    if len(picked) >= 2:
        from apps.knowledge_base.services.compare import diff_information
        pairs = [(m, info_map.get(m, {})) for m in picked]
        base_json["information_diff"] = diff_information(pairs, drop_equal=True)
    else:
        base_json["information_diff"] = {}

    return base_json


async def warmup_intent_router() -> None:
    """
    Прогрев LLM и сервисов поиска.
    """
    from common.openai_client import init_openai_client, warmup_openai

    await init_openai_client()
    await warmup_openai()

    alias = get_alias_search_cached()
    specs = get_specs_search_cached()
    if alias is None or specs is None:
        async with async_session_maker() as session:
            if alias is None:
                await get_alias_search(session)
            if specs is None:
                await get_specs_search(session)
