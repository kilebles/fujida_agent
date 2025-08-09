from sqlalchemy import String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from db.base import Base


class Device(Base):
    __tablename__ = 'devices'

    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String, nullable=False, default='')
    information: Mapped[dict] = mapped_column(JSONB, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)

    aliases: Mapped[list['DeviceAlias']] = relationship(
        back_populates='device',
        cascade='all, delete-orphan',
        lazy='selectin',
    )


class DeviceAlias(Base):
    __tablename__ = 'device_aliases'

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey('devices.id', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    alias: Mapped[str] = mapped_column(String, nullable=False)

    device: Mapped[Device] = relationship(back_populates='aliases')
