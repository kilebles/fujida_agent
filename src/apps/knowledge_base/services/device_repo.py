from __future__ import annotations

from typing import Dict, List, Tuple

from sqlalchemy import select, func, cast
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from db.models import devices as devices_models


class DeviceRepo:
    """
    Репозиторий устройств и их алиасов.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._device_model = getattr(devices_models, "Device", None)
        self._alias_model = getattr(devices_models, "DeviceAlias", None)

    async def list_device_titles(self) -> List[Tuple[int, str]]:
        """
        Возвращает пары (device_id, модель).
        """
        if not self._device_model:
            return []
        res = await self._session.execute(
            select(self._device_model.id, self._device_model.model)
        )
        return [(int(did), str(model)) for did, model in res.all()]

    async def list_alias_pairs(self) -> List[Tuple[str, int]]:
        """
        Возвращает пары (alias, device_id).
        """
        if not self._alias_model:
            return []
        res = await self._session.execute(
            select(self._alias_model.alias, self._alias_model.device_id)
        )
        return [(str(alias), int(device_id)) for alias, device_id in res.all()]

    async def vector_search_by_description(
        self,
        embedding: list[float],
        features: list[str] | None = None,
        top_k: int = 50,
        max_distance: float | None = 0.28,
    ) -> List[Tuple[str, str, float]]:
        """
        Возвращает тройки (model, description, distance). При наличии features применяется фильтрация по подстроке.
        """
        if not self._device_model:
            return []

        distance = func.cosine_distance(
            self._device_model.description_embedding,
            cast(embedding, Vector),
        )

        stmt = select(
            self._device_model.model,
            self._device_model.description,
            distance.label("distance"),
        )

        if features:
            for f in features:
                s = str(f or "").strip()
                if s:
                    stmt = stmt.filter(self._device_model.description.ilike(f"%{s}%"))

        stmt = stmt.order_by(distance.asc()).limit(top_k)

        res = await self._session.execute(stmt)
        rows = [(str(m), str(d), float(dist)) for m, d, dist in res.all()]
        if max_distance is not None:
            rows = [r for r in rows if r[2] <= max_distance]
        return rows

    async def get_information_by_models(self, models: List[str]) -> Dict[str, dict]:
        """
        Возвращает карту model -> information.
        """
        if not self._device_model or not models:
            return {}
        res = await self._session.execute(
            select(self._device_model.model, self._device_model.information).where(
                self._device_model.model.in_(models)
            )
        )
        out: Dict[str, dict] = {}
        for m, info in res.all():
            out[str(m)] = dict(info or {})
        return out
