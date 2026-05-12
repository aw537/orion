"""Convert 5 Integer boolean columns to Boolean type.

Revision ID: 006
Revises: 005
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa


revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL cannot auto-cast integer server defaults to boolean during ALTER COLUMN TYPE.
    # Must explicitly drop the default, change type, then restore a boolean default.
    _bool_cols = [
        ("transition_orientations", "used", "false"),
        ("entity_relationships", "inferred", "false"),
        ("contradictions", "human_reviewed", "false"),
        ("model_profiles", "is_builtin", "true"),
        ("interaction_log", "personal_data", "false"),
    ]
    for table, col, default in _bool_cols:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} DROP DEFAULT")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} TYPE BOOLEAN USING {col}::boolean")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} SET DEFAULT {default}")


def downgrade():
    _int_cols = [
        ("interaction_log", "personal_data", "0"),
        ("model_profiles", "is_builtin", "1"),
        ("contradictions", "human_reviewed", "0"),
        ("entity_relationships", "inferred", "0"),
        ("transition_orientations", "used", "0"),
    ]
    for table, col, default in _int_cols:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} DROP DEFAULT")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} TYPE INTEGER USING {col}::integer")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} SET DEFAULT {default}")
