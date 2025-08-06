"""add devices table manually"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = '03d51956d3cd'
down_revision = '830ea0581c8e'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    op.create_table(
        'devices',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('model', sa.String(), nullable=False, unique=True),
        sa.Column('description', sa.String(), nullable=False, server_default=''),
        sa.Column('information', sa.JSON(), nullable=False),
        sa.Column('embedding', Vector(3072), nullable=False),
    )


def downgrade():
    op.drop_table('devices')
