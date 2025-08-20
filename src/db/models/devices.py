from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from db.base import Base


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("model", name="uq_devices_model"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False, default="")
    information: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description_embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)

    aliases: Mapped[list["DeviceAlias"]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class DeviceAlias(Base):
    __tablename__ = "device_aliases"
    __table_args__ = (
        UniqueConstraint("device_id", "alias", name="uq_device_aliases_device_alias"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    alias: Mapped[str] = mapped_column(String, nullable=False)

    device: Mapped[Device] = relationship(back_populates="aliases")
