"""001_initial_schema — Complete Orion schema.

Squashed from 16 incremental migrations (001-016) into a single file.
No users exist on any database, so this is safe to apply fresh.
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ── Core hierarchy ──

    op.create_table("galaxies",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("owner_agent", sa.Text()),
        sa.Column("strength_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_nodes", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("schema_version", sa.Text(), nullable=False, server_default="001"),
    )

    op.create_table("planets",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("galaxy_id", sa.Text(), sa.ForeignKey("galaxies.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("color", sa.Text(), nullable=False, server_default="#6D28D9"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("stardust_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("health_status", sa.Text(), nullable=False, server_default="healthy"),
        sa.Column("protocol_override", sa.Text()),
    )

    op.create_table("biomes",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("planet_id", sa.Text(), sa.ForeignKey("planets.id"), nullable=False),
        sa.Column("galaxy_id", sa.Text(), sa.ForeignKey("galaxies.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("lifecycle_state", sa.Text(), nullable=False, server_default="SEED"),
        sa.Column("is_inbox", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("last_active_at", sa.DateTime()),
        sa.Column("stardust_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_ttl_seconds", sa.Integer(), nullable=False, server_default="14400"),
    )

    op.create_table("sun_sections",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("galaxy_id", sa.Text(), sa.ForeignKey("galaxies.id"), nullable=False),
        sa.Column("section_key", sa.Text(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("schema_version", sa.Text(), server_default="v0.5"),
    )

    # ── Stardust ──

    op.create_table("stardust",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("biome_id", sa.Text(), sa.ForeignKey("biomes.id"), nullable=False),
        sa.Column("planet_id", sa.Text(), sa.ForeignKey("planets.id"), nullable=False),
        sa.Column("galaxy_id", sa.Text(), sa.ForeignKey("galaxies.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("region", sa.Text(), nullable=False, server_default="contextual"),
        sa.Column("gravity", sa.Text(), nullable=False, server_default="BIOME"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("valid_from", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("valid_until", sa.DateTime()),
        sa.Column("context_tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("contradiction_id", sa.Text()),
        sa.Column("reinforcement_sources", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_agent", sa.Text()),
        sa.Column("chroma_id", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("last_accessed", sa.DateTime()),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reasoning", sa.Text()),
        sa.Column("supersedes", sa.JSON()),
    )
    op.create_index("ix_stardust_biome_id", "stardust", ["biome_id"])
    op.create_index("ix_stardust_planet_id", "stardust", ["planet_id"])
    op.create_index("ix_stardust_galaxy_id", "stardust", ["galaxy_id"])

    # ── Entities & knowledge graph ──

    op.create_table("entities",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("galaxy_id", sa.Text(), sa.ForeignKey("galaxies.id"), nullable=False),
        sa.Column("planet_id", sa.Text(), sa.ForeignKey("planets.id")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("profile", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("mention_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("last_seen", sa.DateTime(), server_default=sa.func.current_timestamp()),
    )
    op.create_index("ix_entities_galaxy_id", "entities", ["galaxy_id"])
    op.create_index("ix_entities_name", "entities", ["name"])
    op.create_index("ix_entities_planet_id", "entities", ["planet_id"])

    op.create_table("entity_stardust",
        sa.Column("entity_id", sa.Text(), primary_key=True),
        sa.Column("stardust_id", sa.Text(), primary_key=True),
        sa.Column("relationship_type", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
    )

    op.create_table("entity_timeline",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("event_date", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("event_content", sa.Text(), nullable=False),
        sa.Column("source_stardust_id", sa.Text()),
    )

    op.create_table("entity_relationships",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("galaxy_id", sa.Text(), nullable=False),
        sa.Column("source_entity_id", sa.Text(), nullable=False),
        sa.Column("target_entity_id", sa.Text(), nullable=False),
        sa.Column("relationship_type", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("valid_from", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("valid_until", sa.DateTime()),
        sa.Column("source_stardust_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("strength", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("inferred", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
    )
    op.create_index("ix_entity_rel_source", "entity_relationships", ["source_entity_id"])
    op.create_index("ix_entity_rel_target", "entity_relationships", ["target_entity_id"])

    op.create_table("entity_backlinks",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("stardust_id", sa.Text(), nullable=False),
        sa.Column("mention_type", sa.Text(), nullable=False, server_default="explicit"),
        sa.Column("mention_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_mention", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("last_mention", sa.DateTime(), server_default=sa.func.current_timestamp()),
    )
    op.create_index("ix_backlinks_entity", "entity_backlinks", ["entity_id"])
    op.create_index("ix_backlinks_stardust", "entity_backlinks", ["stardust_id"])

    op.create_table("stardust_relationships",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("galaxy_id", sa.Text(), nullable=False),
        sa.Column("source_stardust_id", sa.Text(), nullable=False),
        sa.Column("target_stardust_id", sa.Text(), nullable=False),
        sa.Column("relationship_type", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("created_by", sa.Text()),
    )

    op.create_table("graph_path_cache",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("galaxy_id", sa.Text(), nullable=False),
        sa.Column("source_node_id", sa.Text(), nullable=False),
        sa.Column("source_node_type", sa.Text(), nullable=False),
        sa.Column("target_node_id", sa.Text(), nullable=False),
        sa.Column("target_node_type", sa.Text(), nullable=False),
        sa.Column("path", sa.JSON(), nullable=False),
        sa.Column("path_length", sa.Integer(), nullable=False),
        sa.Column("path_types", sa.JSON(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_graph_cache_source", "graph_path_cache", ["source_node_id"])

    # ── Agent identity & brain ──

    op.create_table("agent_identities",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("galaxy_id", sa.Text(), nullable=False),
        sa.Column("agent_name", sa.Text(), nullable=False),
        sa.Column("agent_type", sa.Text(), nullable=False, server_default="GENERAL"),
        sa.Column("model_family", sa.Text()),
        sa.Column("current_model", sa.Text()),
        sa.Column("birth_date", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("total_sessions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_reads", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_writes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens_consumed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("knowledge_contribution_score", sa.Float(), server_default="0.0"),
        sa.Column("retrieval_quality_score", sa.Float(), server_default="0.0"),
        sa.Column("contradiction_rate", sa.Float(), server_default="0.0"),
        sa.Column("calibration_score", sa.Float(), server_default="0.0"),
        sa.Column("last_active", sa.DateTime()),
        sa.Column("personality_snapshot", sa.Text()),
        sa.Column("expertise_profile", sa.JSON(), server_default="{}"),
        sa.UniqueConstraint("galaxy_id", "agent_name", name="uq_agent_galaxy_name"),
    )

    op.create_table("agent_sessions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("agent_identity_id", sa.Text(), nullable=False),
        sa.Column("galaxy_id", sa.Text(), nullable=False),
        sa.Column("model_used", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("ended_at", sa.DateTime()),
        sa.Column("reads", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("writes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_consumed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("context_bundles_served", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("biomes_accessed", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("knowledge_gained", sa.Text()),
        sa.Column("session_quality_score", sa.Float()),
        sa.Column("model_switch_from", sa.Text()),
        sa.Column("galaxy_strength_at_start", sa.Float()),
    )
    op.create_index("ix_agent_sessions_identity", "agent_sessions", ["agent_identity_id"])

    op.create_table("agent_expertise",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("agent_identity_id", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("expertise_level", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_demonstrated", sa.DateTime()),
    )

    op.create_table("model_switch_log",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("agent_identity_id", sa.Text(), nullable=False),
        sa.Column("galaxy_id", sa.Text(), nullable=False),
        sa.Column("previous_model", sa.Text(), nullable=False),
        sa.Column("new_model", sa.Text(), nullable=False),
        sa.Column("switched_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("reason", sa.Text(), server_default="user_configured"),
        sa.Column("continuity_score", sa.Float()),
        sa.Column("compatibility_issues", sa.Text()),
        sa.Column("transition_orientation_id", sa.Text()),
    )

    op.create_table("transition_orientations",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("model_switch_id", sa.Text(), nullable=False),
        sa.Column("agent_identity_id", sa.Text(), nullable=False),
        sa.Column("from_model", sa.Text(), nullable=False),
        sa.Column("to_model", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("orientation_content", sa.Text(), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table("session_calibrations",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("agent_identity_id", sa.Text(), nullable=False),
        sa.Column("galaxy_id", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("records_used", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("records_retrieved_unused", sa.JSON(), server_default="[]"),
        sa.Column("knowledge_gaps", sa.JSON(), server_default="[]"),
        sa.Column("session_outcome", sa.Text()),
        sa.Column("knowledge_quality_score", sa.Float()),
        sa.Column("most_useful_regions", sa.JSON(), server_default="[]"),
        sa.Column("least_useful_regions", sa.JSON(), server_default="[]"),
    )

    op.create_table("knowledge_integration_log",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("stardust_id", sa.Text(), nullable=False),
        sa.Column("agent_identity_id", sa.Text(), nullable=False),
        sa.Column("integrated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("contradictions_detected", sa.Integer(), server_default="0"),
        sa.Column("supersessions_processed", sa.Integer(), server_default="0"),
        sa.Column("expertise_domains_updated", sa.JSON(), server_default="[]"),
        sa.Column("compiled_truth_updated", sa.Integer(), server_default="0"),
        sa.Column("adjacencies_flagged", sa.Integer(), server_default="0"),
        sa.Column("relationships_extracted", sa.Integer(), server_default="0"),
        sa.Column("integration_duration_ms", sa.Integer()),
    )

    # ── Contradictions, activity log, strength ──

    op.create_table("contradictions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("galaxy_id", sa.Text(), nullable=False),
        sa.Column("region", sa.Text()),
        sa.Column("record_a_id", sa.Text()),
        sa.Column("record_b_id", sa.Text()),
        sa.Column("conflict_type", sa.Text(), nullable=False),
        sa.Column("context_a", sa.Text()),
        sa.Column("context_b", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="UNRESOLVED"),
        sa.Column("detected_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("detected_by", sa.Text()),
        sa.Column("resolved_at", sa.DateTime()),
        sa.Column("resolved_by", sa.Text()),
        sa.Column("resolution_note", sa.Text()),
        sa.Column("human_reviewed", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table("interaction_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("galaxy_id", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text()),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("initiated_by", sa.Text(), nullable=False),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("planet_id", sa.Text()),
        sa.Column("biome_id", sa.Text()),
        sa.Column("region", sa.Text()),
        sa.Column("record_id", sa.Text()),
        sa.Column("payload_before", sa.Text()),
        sa.Column("payload_after", sa.Text()),
        sa.Column("confidence_delta", sa.Float()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("cache_hit", sa.Integer()),
        sa.Column("personal_data", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table("strength_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("galaxy_id", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("volume_score", sa.Float(), nullable=False),
        sa.Column("density_score", sa.Float(), nullable=False),
        sa.Column("health_score", sa.Float(), nullable=False),
        sa.Column("diversity_score", sa.Float(), nullable=False),
        sa.Column("coverage_score", sa.Float(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
    )

    # ── Model profiles, subagents, audit ──

    op.create_table("model_profiles",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("model_id", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("context_window_tokens", sa.Integer(), nullable=False),
        sa.Column("optimal_context_tokens", sa.Integer(), nullable=False),
        sa.Column("format_preference", sa.Text(), nullable=False, server_default="structured_json"),
        sa.Column("tool_calling", sa.Text(), nullable=False, server_default="native"),
        sa.Column("is_builtin", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
    )

    op.create_table("subagents",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("galaxy_id", sa.Text(), nullable=False),
        sa.Column("agent_name", sa.Text(), nullable=False),
        sa.Column("model", sa.Text()),
        sa.Column("planet_scope", sa.Text()),
        sa.Column("biome_scope", sa.Text(), nullable=False, server_default='["*"]'),
        sa.Column("trust_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("write_authority", sa.Text(), nullable=False, server_default="CACHE_ONLY"),
        sa.Column("session_id", sa.Text()),
        sa.Column("registered_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("last_active", sa.DateTime()),
        sa.Column("total_reads", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_writes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("contradiction_rate", sa.Float(), server_default="0.0"),
        sa.Column("agent_identity_id", sa.Text()),
    )

    op.create_table("subagent_sessions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("subagent_id", sa.Text(), nullable=False),
        sa.Column("model_profile_id", sa.Text()),
        sa.Column("session_token", sa.Text(), nullable=False, unique=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("last_active", sa.DateTime()),
        sa.Column("context_bundles_served", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens_served", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table("audit_runs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("galaxy_id", sa.Text(), nullable=False),
        sa.Column("run_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("run_by", sa.Text(), nullable=False, server_default="audit_ai"),
        sa.Column("records_reviewed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates_merged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("contradictions_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("contradictions_classified", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("promotions_made", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence_decays", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("summary", sa.Text()),
    )

    op.create_table("schema_versions",
        sa.Column("version_id", sa.Text(), primary_key=True),
        sa.Column("applied_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("checksum", sa.Text(), nullable=False),
    )

    op.create_table("gravity_bridges",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("galaxy_id", sa.Text(), nullable=False),
        sa.Column("source_planet_id", sa.Text(), nullable=False),
        sa.Column("target_planet_id", sa.Text(), nullable=False),
        sa.Column("bridge_type", sa.Text(), nullable=False),
        sa.Column("opened_by", sa.Text()),
        sa.Column("opened_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("revoked_at", sa.DateTime()),
        sa.Column("scope_constraints", sa.Text()),
        sa.Column("traversal_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_galaxy_id", sa.Text()),
    )

    # ── Users, auth, RBAC ──

    op.create_table("users",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("last_login", sa.DateTime()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("role", sa.Text(), nullable=False, server_default="owner"),
        sa.Column("galaxy_id", sa.Text(), sa.ForeignKey("galaxies.id")),
        sa.Column("planet_id", sa.Text(), sa.ForeignKey("planets.id")),
        sa.Column("preferences", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("api_key", sa.Text(), unique=True),
        sa.Column("api_key_created_at", sa.DateTime()),
    )

    op.create_table("user_sessions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("last_used", sa.DateTime()),
        sa.Column("user_agent", sa.Text()),
        sa.Column("ip_address", sa.Text()),
    )

    op.create_table("planet_access_grants",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("planet_id", sa.Text(), sa.ForeignKey("planets.id"), nullable=False),
        sa.Column("access_type", sa.Text(), nullable=False),
        sa.Column("granted_by", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("granted_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("expires_at", sa.DateTime()),
        sa.UniqueConstraint("user_id", "planet_id", name="uq_user_planet_grant"),
    )

    op.create_table("permission_checks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("permitted", sa.Boolean(), nullable=False),
        sa.Column("checked_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("denial_reason", sa.Text()),
    )

    op.create_table("galaxy_invites",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("galaxy_id", sa.Text(), sa.ForeignKey("galaxies.id"), nullable=False),
        sa.Column("planet_id", sa.Text(), sa.ForeignKey("planets.id")),
        sa.Column("invited_by", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="member"),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime()),
        sa.Column("used_by", sa.Text(), sa.ForeignKey("users.id")),
    )

    # ── Galaxy merge ──

    op.create_table("merge_proposals",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("source_galaxy_id", sa.Text(), sa.ForeignKey("galaxies.id"), nullable=False),
        sa.Column("target_galaxy_id", sa.Text(), sa.ForeignKey("galaxies.id"), nullable=False),
        sa.Column("proposed_by", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("accepted_by", sa.Text(), sa.ForeignKey("users.id")),
        sa.Column("status", sa.Text(), nullable=False, server_default="proposed"),
        sa.Column("merged_sun", sa.Text()),
        sa.Column("entity_mappings_count", sa.Integer(), server_default="0"),
        sa.Column("bridges_created", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("rejection_reason", sa.Text()),
    )

    op.create_table("entity_merge_mappings",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("proposal_id", sa.Text(), sa.ForeignKey("merge_proposals.id"), nullable=False),
        sa.Column("source_entity_id", sa.Text(), sa.ForeignKey("entities.id"), nullable=False),
        sa.Column("target_entity_id", sa.Text(), sa.ForeignKey("entities.id"), nullable=False),
        sa.Column("match_type", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("merged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
    )

    # ── Routing ──

    op.create_table("routing_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("galaxy_id", sa.Text(), nullable=False),
        sa.Column("stardust_id", sa.Text(), sa.ForeignKey("stardust.id"), nullable=False),
        sa.Column("routed_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("caller_suggested_planet", sa.Text()),
        sa.Column("caller_suggested_biome", sa.Text()),
        sa.Column("assigned_planet_id", sa.Text(), sa.ForeignKey("planets.id"), nullable=False),
        sa.Column("assigned_biome_id", sa.Text(), sa.ForeignKey("biomes.id")),
        sa.Column("routing_method", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reasoning", sa.Text()),
        sa.Column("graphify_cluster", sa.Text()),
        sa.Column("corrected_planet_id", sa.Text(), sa.ForeignKey("planets.id")),
        sa.Column("corrected_at", sa.DateTime()),
        sa.Column("corrected_by", sa.Text()),
    )
    op.create_index("idx_routing_log_galaxy", "routing_log", ["galaxy_id"])
    op.create_index("idx_routing_log_stardust", "routing_log", ["stardust_id"])
    op.create_index("idx_routing_log_method", "routing_log", ["routing_method"])


def downgrade():
    # Single migration — downgrade drops everything.
    for table in reversed([
        "routing_log", "entity_merge_mappings", "merge_proposals",
        "galaxy_invites", "permission_checks", "planet_access_grants",
        "user_sessions", "users", "gravity_bridges", "schema_versions",
        "audit_runs", "subagent_sessions", "subagents", "model_profiles",
        "strength_history", "interaction_log", "contradictions",
        "knowledge_integration_log", "session_calibrations",
        "transition_orientations", "model_switch_log", "agent_expertise",
        "agent_sessions", "agent_identities", "graph_path_cache",
        "stardust_relationships", "entity_backlinks", "entity_relationships",
        "entity_timeline", "entity_stardust", "entities",
        "stardust", "sun_sections", "biomes", "planets", "galaxies",
    ]):
        op.drop_table(table)
