import json
import re
import time
from typing import Any, Dict, List

from common.openai_client import openai_client
from db.session import async_session_maker
from apps.knowledge_base.services.alias_search import (
    get_alias_search,
    get_alias_search_cached,
)


PROMPT = (
    "Ты маршрутизатор запросов о продуктах Fujida."
    "Всегда отвечай строго JSON."
    "Ключи: route ∈ {by_name, by_specs, by_faq}, user_query, models, features."
    "models — список ПОЛНЫХ имён моделей (без бренда «fujida», латиницей, в нижнем регистре)."
    "features — список характеристик или функций (на русском или английском),"
    "актуально только для route = \"by_specs\". Если в запросе встречаются характеристики,"
    "сохраняй их в естественном виде: «глонасс» остаётся «глонасс», «задняя камера» остаётся «задняя камера»."
    "Технические термины типа «wifi», «128gb microsd» можно оставить латиницей."
    "Разделяй разные модели только если в запросе явно есть разделители: запятая, «или»,"
    "«либо», «vs», «против», «/», «|»."
    "Допустимые модификаторы моделей: max, pro, duo, ai, wifi, s, se, smart, hit, blik, bliss."
    "Исправляй ошибки в модификаторах: луо→duo, крмв→karma."
    "Кириллицу транслитерируй только в названиях моделей: зум→zoom, карма→karma, хит→hit, блисс/блис→bliss, блик→blik,"
    "смарт→smart, макс→max, про→pro, дуо→duo, вайфай/вифи/ви-фи→wifi, эс/с→s, се/сэ→se."
    "Примеры классификации:"
    "  route = \"by_name\" — сравнение или выбор между конкретными моделями, а также запросы об описании или характеристиках конкретной модели:"
    "    «зум хит с луо» → models = [\"zoom hit s duo\"], features = []."
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


_ALLOWED_ROUTES = {"by_name", "by_specs, by_faq".split(", ")[0], "by_faq"}
_LLM_CACHE_TTL = 60.0
_LLM_CACHE_MAX = 512
MAX_ALIAS_CANDIDATES = 12


def _split_disjunctions(text: str) -> List[str]:
    """
    Делит исходный текст на куски по явным разделителям моделей.
    """
    pat = re.compile(r"\b(от|и|или|либо|vs\.?|против)\b|[\/\|,;]",
                     flags=re.IGNORECASE)
    parts = [p.strip() for p in pat.split(text) if p]
    out: List[str] = []
    for p in parts:
        if pat.match(p):
            continue
        if p:
            out.append(p)
    return out


def _norm_ascii_ru2en(s: str) -> str:
    """
    Нормализует строку к латинице в нижнем регистре с подменой русских
    синонимов.
    """
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
    """
    Возвращает кэшированный ответ LLM.
    """
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
    """
    Сохраняет ответ LLM в кэш.
    """
    if len(_llm_cache) >= _LLM_CACHE_MAX:
        _llm_cache.pop(next(iter(_llm_cache)))
    _llm_cache[key] = (time.time(), value)


def _normalize_llm_output(parsed: Dict[str, Any],
                          user_query: str) -> Dict[str, Any]:
    """
    Приводит ответ модели к допустимому формату и склеивает фрагменты,
    если LLM раздробил модель.
    """
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
            piece = " ".join(model_tokens[pos: pos + want]).strip()
            if piece:
                merged.append(piece)
            pos += want
        if len(merged) == len(chunks):
            models = merged

    parsed["route"] = route
    parsed["user_query"] = parsed.get("user_query") or user_query
    parsed["models"] = models
    return parsed


async def _route_with_llm(user_query: str) -> Dict[str, Any]:
    """
    Запрашивает LLM в JSON-режиме, нормализует ответ и кэширует его.
    """
    cached = _cache_get(user_query)
    if cached is not None:
        return cached

    resp = await openai_client.chat.completions.create(
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
        raw = {"route": "by_faq", "user_query": user_query, "models": []}

    parsed = _normalize_llm_output(raw, user_query)
    _cache_set(user_query, parsed)
    return parsed


async def route_intent_llm(user_query: str) -> Dict[str, Any]:
    base_json = await _route_with_llm(user_query)
    route = base_json.get("route")
    models = base_json.get("models", []) or []

    if route == "by_faq":
        base_json["found_models"] = []
        return base_json

    if route == "by_specs" and not models:
        base_json["found_models"] = []
        return base_json

    svc = get_alias_search_cached()
    if svc is None:
        async with async_session_maker() as session:
            svc = await get_alias_search(session)

    decisions = await svc.resolve_for_router(
        models,
        max_candidates=MAX_ALIAS_CANDIDATES,
    )

    found_models: List[Dict[str, Any]] = []
    for d in decisions:
        found_models.append(
            {
                "model": d.get("picked"),
                "candidates": d.get("candidates", []),
            }
        )

    base_json["found_models"] = found_models
    return base_json
