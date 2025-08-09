import logging
import json
from typing import List

from sqlalchemy import select, func, cast, desc, text
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from db.models.devices import Device, DeviceAlias
from db.session import async_session_maker
from common.openai_client import openai_client
from utils.text import normalize
from apps.knowledge_base.prompt_template import build_knowledge_prompt

logger = logging.getLogger(__name__)


async def _alias_exact(session: AsyncSession, qn: str, limit: int) -> List[Device]:
    stmt = (
        select(Device)
        .join(DeviceAlias, DeviceAlias.device_id == Device.id)
        .where(DeviceAlias.alias == qn)
        .limit(limit)
    )
    rows = await session.execute(stmt)
    devices = rows.scalars().all()
    logger.info(f"[Exact Alias Search] '{qn}' → {len(devices)} результатов: {[d.model for d in devices]}")
    return devices


async def _alias_trgm(session: AsyncSession, qn: str, limit: int, threshold: float) -> List[Device]:
    sim = func.similarity(DeviceAlias.alias, qn)
    stmt = (
        select(Device)
        .join(DeviceAlias, DeviceAlias.device_id == Device.id)
        .where(sim > threshold)
        .order_by(desc(sim))
        .limit(limit)
    )
    rows = await session.execute(stmt)
    devices = rows.scalars().all()
    logger.info(f"[Trigram Alias Search] '{qn}' (threshold={threshold}) → {len(devices)} результатов: {[d.model for d in devices]}")
    return devices


async def _vector_search(session: AsyncSession, query: str, limit: int) -> List[Device]:
    r = await openai_client.embeddings.create(input=query, model="text-embedding-3-small")
    emb = r.data[0].embedding
    stmt = (
        select(Device)
        .order_by(func.cosine_distance(Device.embedding, cast(emb, Vector)))
        .limit(limit)
    )
    rows = await session.execute(stmt)
    devices = rows.scalars().all()
    logger.info(f"[Vector Search] '{query}' → {len(devices)} результатов: {[d.model for d in devices]}")
    return devices


def _dedup_keep_order(items: List[Device]) -> List[Device]:
    seen = set()
    out: List[Device] = []
    for d in items:
        if d.id in seen:
            continue
        seen.add(d.id)
        out.append(d)
    return out


async def search_devices(query: str, session: AsyncSession, top_n: int = 5, trgm_threshold: float = 0.42) -> List[Device]:
    qn = normalize(query)
    logger.info(f"[Search Start] Query: '{query}' → Normalized: '{qn}'")

    exact = await _alias_exact(session, qn, top_n)
    if len(exact) >= top_n:
        logger.info("[Search Result] Достаточно точных совпадений, возвращаем результат.")
        return exact[:top_n]

    trgm_needed = top_n * 3
    trgm = await _alias_trgm(session, qn, trgm_needed, trgm_threshold)
    merged = _dedup_keep_order(exact + trgm)
    if len(merged) >= top_n:
        logger.info("[Search Result] Достаточно результатов после триграм-поиска.")
        return merged[:top_n]

    vec = await _vector_search(session, query, top_n * 3)
    final = _dedup_keep_order(merged + vec)
    logger.info(f"[Search Result] Итог: {[d.model for d in final[:top_n]]}")
    return final[:top_n]


def build_context(devices: list[Device]) -> str:
    def format_info(info: dict) -> str:
        return "\n".join(f"- *{key}*: {value}" for key, value in info.items())

    return "\n\n".join(
        f"{device.model}\n\n"
        f"{device.description}\n\n"
        f"{format_info(device.information)}"
        for device in devices
    )


async def generate_device_response(user_message: str) -> str:
    """
    Возвращает ответ на вопрос пользователя о моделях Fujida.
    """
    async with async_session_maker() as session:
        all_models_result = await session.execute(select(Device.model))
        all_models = [m[0] for m in all_models_result.all()]
        mentioned = extract_model_names(user_message, all_models)

        if len(mentioned) >= 2:
            stmt = select(Device).where(Device.model.in_(mentioned))
            result = await session.execute(stmt)
            devices = result.scalars().all()
            context = "\n\n".join(
                f"{d.model}:\n{d.description}\nХарактеристики: {json.dumps(d.information, ensure_ascii=False)}"
                for d in devices
            )
        else:
            devices = await search_devices(user_message, session)
            context = "\n\n".join(f"{d.model}:\n{d.description}" for d in devices)

    prompt = build_knowledge_prompt(context, user_message)
    r = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )
    return r.choices[0].message.content
