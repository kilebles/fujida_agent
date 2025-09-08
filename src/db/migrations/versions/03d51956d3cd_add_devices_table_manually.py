"""add devices with vector text and embeddings"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "03d51956d3cd"
down_revision = "830ea0581c8e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model", sa.String(), nullable=False, unique=True),
        sa.Column("vector_text", sa.String(), nullable=False, server_default=""),
        sa.Column("vector", Vector(3072), nullable=False),
    )

    op.alter_column("devices", "vector_text", server_default=None)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS device_aliases CASCADE")
    op.drop_table("devices")