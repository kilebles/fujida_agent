"""add faq table manually"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "830ea0581c8e"
down_revision = "6814e7e39529"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "faq_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question", sa.String(), nullable=False, unique=True),
        sa.Column("answer", sa.String(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("faq_entries")