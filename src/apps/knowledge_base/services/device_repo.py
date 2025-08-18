from __future__ import annotations

from typing import List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import devices as devices_models


class DeviceRepo:
    """
    Репозиторий устройств и их алиасов. Источник данных — БД.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._device_model = getattr(devices_models, "Device", None)
        self._alias_model = getattr(devices_models, "DeviceAlias", None)

    async def list_device_titles(self) -> List[Tuple[int, str]]:
        """
        Возвращает пары (device_id, модель) из БД.
        """
        if not self._device_model:
            return []
        res = await self._session.execute(
            select(self._device_model.id, self._device_model.model)
        )
        return [(int(did), str(model)) for did, model in res.all()]

    async def list_alias_pairs(self) -> List[Tuple[str, int]]:
        """
        Возвращает пары (alias, device_id) из БД.
        """
        if not self._alias_model:
            return []
        res = await self._session.execute(
            select(self._alias_model.alias, self._alias_model.device_id)
        )
        return [(str(alias), int(device_id)) for alias, device_id in res.all()]
