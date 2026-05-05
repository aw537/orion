"""002 — Merge phase flags + contradiction dedup constraint.

- Adds reconciliation_done / bridging_done booleans to merge_proposals so
  execute_merge can skip phases that already ran even when their counts are zero.
- Deduplicates existing contradiction pairs and adds a unique constraint on
  (record_a_id, record_b_id) to prevent re-insertion across audit runs.
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    # ── merge_proposals phase flags ──────────────────────────────────
    op.add_column("merge_proposals",
        sa.Column("reconciliation_done", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("merge_proposals",
        sa.Column("bridging_done", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.execute("UPDATE merge_proposals SET reconciliation_done = 1 WHERE entity_mappings_count > 0")
    op.execute("UPDATE merge_proposals SET bridging_done = 1 WHERE bridges_created > 0")
    op.execute("UPDATE merge_proposals SET reconciliation_done = 1, bridging_done = 1 WHERE status = 'complete'")

    # ── contradictions unique pair ───────────────────────────────────
    # Remove duplicates, keeping the oldest row per canonical (min_id, max_id) pair.
    op.execute("""
        DELETE FROM contradictions
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM contradictions
            GROUP BY
                CASE WHEN record_a_id < record_b_id THEN record_a_id ELSE record_b_id END,
                CASE WHEN record_a_id < record_b_id THEN record_b_id ELSE record_a_id END
        )
    """)

    op.create_unique_constraint(
        "uq_contradiction_pair", "contradictions", ["record_a_id", "record_b_id"]
    )


def downgrade():
    op.drop_constraint("uq_contradiction_pair", "contradictions", type_="unique")
    op.drop_column("merge_proposals", "bridging_done")
    op.drop_column("merge_proposals", "reconciliation_done")
