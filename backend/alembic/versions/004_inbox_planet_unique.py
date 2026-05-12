"""partial unique index: one inbox planet per galaxy

Revision ID: 004
Revises: 003
Create Date: 2026-05-11
"""
from alembic import op

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_planets_inbox_per_galaxy "
        "ON planets (galaxy_id) WHERE planet_type = 'inbox'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_planets_inbox_per_galaxy")
