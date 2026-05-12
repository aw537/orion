"""add last_decayed_at to stardust

Revision ID: 003
Revises: 002
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('stardust', sa.Column('last_decayed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('stardust', 'last_decayed_at')
