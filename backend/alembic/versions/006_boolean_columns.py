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
    op.alter_column(
        "transition_orientations", "used",
        existing_type=sa.Integer(),
        type_=sa.Boolean(),
        existing_nullable=False,
        postgresql_using="used::boolean",
    )
    op.alter_column(
        "entity_relationships", "inferred",
        existing_type=sa.Integer(),
        type_=sa.Boolean(),
        existing_nullable=False,
        postgresql_using="inferred::boolean",
    )
    op.alter_column(
        "contradictions", "human_reviewed",
        existing_type=sa.Integer(),
        type_=sa.Boolean(),
        existing_nullable=False,
        postgresql_using="human_reviewed::boolean",
    )
    op.alter_column(
        "model_profiles", "is_builtin",
        existing_type=sa.Integer(),
        type_=sa.Boolean(),
        existing_nullable=False,
        postgresql_using="is_builtin::boolean",
    )
    op.alter_column(
        "interaction_log", "personal_data",
        existing_type=sa.Integer(),
        type_=sa.Boolean(),
        existing_nullable=False,
        postgresql_using="personal_data::boolean",
    )


def downgrade():
    op.alter_column("interaction_log", "personal_data", existing_type=sa.Boolean(), type_=sa.Integer(), existing_nullable=False)
    op.alter_column("model_profiles", "is_builtin", existing_type=sa.Boolean(), type_=sa.Integer(), existing_nullable=False)
    op.alter_column("contradictions", "human_reviewed", existing_type=sa.Boolean(), type_=sa.Integer(), existing_nullable=False)
    op.alter_column("entity_relationships", "inferred", existing_type=sa.Boolean(), type_=sa.Integer(), existing_nullable=False)
    op.alter_column("transition_orientations", "used", existing_type=sa.Boolean(), type_=sa.Integer(), existing_nullable=False)
