"""Add FK constraints to routing_log and graph_path_cache; drop orphaned tables.

Revision ID: 005
Revises: 004
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    # Safety: delete orphaned rows before adding constraints
    op.execute(
        "DELETE FROM routing_log WHERE galaxy_id NOT IN (SELECT id FROM galaxies)"
    )
    op.execute(
        "DELETE FROM graph_path_cache WHERE galaxy_id NOT IN (SELECT id FROM galaxies)"
    )

    op.create_foreign_key(
        "fk_routing_log_galaxy_id", "routing_log",
        "galaxies", ["galaxy_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_graph_path_cache_galaxy_id", "graph_path_cache",
        "galaxies", ["galaxy_id"], ["id"],
    )

    # Drop orphaned tables whose Python model classes have been removed
    op.drop_table("subagent_sessions")
    op.drop_table("subagents")


def downgrade():
    op.drop_constraint("fk_graph_path_cache_galaxy_id", "graph_path_cache", type_="foreignkey")
    op.drop_constraint("fk_routing_log_galaxy_id", "routing_log", type_="foreignkey")

    op.create_table(
        "subagents",
        sa.Column("id", sa.Text(), nullable=False, primary_key=True),
        sa.Column("galaxy_id", sa.Text(), nullable=False),
        sa.Column("agent_name", sa.Text(), nullable=False),
        sa.Column("model", sa.Text()),
        sa.Column("planet_scope", sa.Text()),
        sa.Column("biome_scope", sa.Text(), server_default='["*"]'),
        sa.Column("trust_level", sa.Integer(), server_default="1"),
        sa.Column("write_authority", sa.Text(), server_default="CACHE_ONLY"),
        sa.Column("session_id", sa.Text()),
        sa.Column("registered_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_active", sa.DateTime()),
        sa.Column("total_reads", sa.Integer(), server_default="0"),
        sa.Column("total_writes", sa.Integer(), server_default="0"),
        sa.Column("contradiction_rate", sa.Float(), server_default="0.0"),
        sa.Column("agent_identity_id", sa.Text()),
    )
    op.create_table(
        "subagent_sessions",
        sa.Column("id", sa.Text(), nullable=False, primary_key=True),
        sa.Column("subagent_id", sa.Text(), nullable=False),
        sa.Column("model_profile_id", sa.Text()),
        sa.Column("session_token", sa.Text(), nullable=False, unique=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_active", sa.DateTime()),
        sa.Column("context_bundles_served", sa.Integer(), server_default="0"),
        sa.Column("total_tokens_served", sa.Integer(), server_default="0"),
    )
