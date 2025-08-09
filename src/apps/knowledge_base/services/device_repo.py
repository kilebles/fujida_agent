from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.devices import Device, DeviceAlias


class DeviceRepo:
    """Доступ к устройствам и алиасам."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_alias_pairs(self) -> Sequence[tuple[str, int]]:
        """Возвращает пары (alias, device_id) для активного словаря."""
        stmt = select(DeviceAlias.alias, DeviceAlias.device_id)
        res = await self.session.execute(stmt)
        return res.all()

    async def list_device_titles(self) -> Sequence[tuple[int, str]]:
        """Возвращает пары (device_id, model)."""
        stmt = select(Device.id, Device.model)
        res = await self.session.execute(stmt)
        return res.all()
