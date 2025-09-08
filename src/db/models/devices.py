from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from db.base import Base


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("model", name="uq_devices_model"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    vector_text: Mapped[str] = mapped_column(String, nullable=False, default="")
    vector: Mapped[list[float]] = mapped_column(Vector(3072), nullable=False)