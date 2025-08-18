"""add devices with split embeddings"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

revision: str = '03d51956d3cd'
down_revision = '830ea0581c8e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')

    op.create_table(
        'devices',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('model', sa.String(), nullable=False, unique=True),
        sa.Column('description', sa.String(), nullable=False, server_default=''),
        sa.Column('information', JSONB, nullable=False),
        sa.Column('model_name_embedding', Vector(1536), nullable=False),
        sa.Column('description_embedding', Vector(1536), nullable=False),
    )

    op.create_table(
        'device_aliases',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('device_id', sa.Integer(), sa.ForeignKey('devices.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('alias', sa.String(), nullable=False),
    )

    op.create_unique_constraint('uq_device_aliases_device_alias', 'device_aliases', ['device_id', 'alias'])
    op.execute("""
        CREATE INDEX ix_device_aliases_alias_trgm
        ON device_aliases
        USING gin (alias gin_trgm_ops)
    """)

    op.execute("""
        CREATE INDEX idx_devices_model_name_embedding_ivfflat
        ON devices
        USING ivfflat (model_name_embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    op.execute("""
        CREATE INDEX idx_devices_description_embedding_ivfflat
        ON devices
        USING ivfflat (description_embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    op.alter_column('devices', 'description', server_default=None)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_devices_description_embedding_ivfflat")
    op.execute("DROP INDEX IF EXISTS idx_devices_model_name_embedding_ivfflat")
    op.execute("DROP INDEX IF EXISTS ix_device_aliases_alias_trgm")
    op.drop_constraint('uq_device_aliases_device_alias', 'device_aliases', type_='unique')
    op.drop_table('device_aliases')
    op.drop_table('devices')
