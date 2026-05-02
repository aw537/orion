from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text, Integer, Float, DateTime, UniqueConstraint, JSON, ForeignKey, func
from datetime import datetime
from app.models.galaxy import Base


class AgentIdentity(Base):
    __tablename__ = "agent_identities"
    __table_args__ = (UniqueConstraint("galaxy_id", "agent_name", name="uq_agent_galaxy_name"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False)
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    agent_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="GENERAL")
    model_family: Mapped[str | None] = mapped_column(Text)
    current_model: Mapped[str | None] = mapped_column(Text)
    birth_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    total_sessions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_reads: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_writes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_tokens_consumed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    knowledge_contribution_score: Mapped[float] = mapped_column(Float, server_default="0.0")
    retrieval_quality_score: Mapped[float] = mapped_column(Float, server_default="0.0")
    contradiction_rate: Mapped[float] = mapped_column(Float, server_default="0.0")
    calibration_score: Mapped[float] = mapped_column(Float, server_default="0.0")
    last_active: Mapped[datetime | None] = mapped_column(DateTime)
    personality_snapshot: Mapped[str | None] = mapped_column(Text)
    expertise_profile: Mapped[dict] = mapped_column(JSON, server_default="{}")


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    agent_identity_id: Mapped[str] = mapped_column(Text, ForeignKey("agent_identities.id"), nullable=False, index=True)
    galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False)
    model_used: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    reads: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    writes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    tokens_consumed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    context_bundles_served: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    biomes_accessed: Mapped[list] = mapped_column(JSON, nullable=False, server_default="[]")
    knowledge_gained: Mapped[str | None] = mapped_column(Text)
    session_quality_score: Mapped[float | None] = mapped_column(Float)
    model_switch_from: Mapped[str | None] = mapped_column(Text)
    galaxy_strength_at_start: Mapped[float | None] = mapped_column(Float)


class AgentExpertise(Base):
    __tablename__ = "agent_expertise"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    agent_identity_id: Mapped[str] = mapped_column(Text, ForeignKey("agent_identities.id"), nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    expertise_level: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_demonstrated: Mapped[datetime | None] = mapped_column(DateTime)


class ModelSwitchLog(Base):
    __tablename__ = "model_switch_log"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    agent_identity_id: Mapped[str] = mapped_column(Text, ForeignKey("agent_identities.id"), nullable=False)
    galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False)
    previous_model: Mapped[str] = mapped_column(Text, nullable=False)
    new_model: Mapped[str] = mapped_column(Text, nullable=False)
    switched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    reason: Mapped[str | None] = mapped_column(Text, server_default="user_configured")
    continuity_score: Mapped[float | None] = mapped_column(Float)
    compatibility_issues: Mapped[str | None] = mapped_column(Text)
    transition_orientation_id: Mapped[str | None] = mapped_column(Text)


class TransitionOrientation(Base):
    __tablename__ = "transition_orientations"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    model_switch_id: Mapped[str] = mapped_column(Text, ForeignKey("model_switch_log.id"), nullable=False)
    agent_identity_id: Mapped[str] = mapped_column(Text, ForeignKey("agent_identities.id"), nullable=False)
    from_model: Mapped[str] = mapped_column(Text, nullable=False)
    to_model: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    orientation_content: Mapped[str] = mapped_column(Text, nullable=False)
    # TODO: Boolean stored as Integer (SQLite compat). Migrate to Boolean column type
    # when adding proper boolean support across all models (see also: EntityRelationship.inferred,
    # Contradiction.human_reviewed, InteractionLog.personal_data, ModelProfile.is_builtin).
    used: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class SessionCalibration(Base):
    __tablename__ = "session_calibrations"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    # No FK on session_id/agent_identity_id: onboarding uses sentinel value "onboarding"
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    agent_identity_id: Mapped[str] = mapped_column(Text, nullable=False)
    galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    records_used: Mapped[list] = mapped_column(JSON, nullable=False, server_default="[]")
    records_retrieved_unused: Mapped[list] = mapped_column(JSON, server_default="[]")
    knowledge_gaps: Mapped[list] = mapped_column(JSON, server_default="[]")
    session_outcome: Mapped[str | None] = mapped_column(Text)
    knowledge_quality_score: Mapped[float | None] = mapped_column(Float)
    most_useful_regions: Mapped[list] = mapped_column(JSON, server_default="[]")
    least_useful_regions: Mapped[list] = mapped_column(JSON, server_default="[]")


class KnowledgeIntegrationLog(Base):
    __tablename__ = "knowledge_integration_log"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    stardust_id: Mapped[str] = mapped_column(Text, ForeignKey("stardust.id"), nullable=False)
    agent_identity_id: Mapped[str] = mapped_column(Text, ForeignKey("agent_identities.id"), nullable=False)
    integrated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    contradictions_detected: Mapped[int] = mapped_column(Integer, server_default="0")
    supersessions_processed: Mapped[int] = mapped_column(Integer, server_default="0")
    expertise_domains_updated: Mapped[list] = mapped_column(JSON, server_default="[]")
    compiled_truth_updated: Mapped[int] = mapped_column(Integer, server_default="0")
    adjacencies_flagged: Mapped[int] = mapped_column(Integer, server_default="0")
    relationships_extracted: Mapped[int] = mapped_column(Integer, server_default="0")
    integration_duration_ms: Mapped[int | None] = mapped_column(Integer)


class EntityRelationship(Base):
    __tablename__ = "entity_relationships"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False)
    source_entity_id: Mapped[str] = mapped_column(Text, ForeignKey("entities.id"), nullable=False, index=True)
    target_entity_id: Mapped[str] = mapped_column(Text, ForeignKey("entities.id"), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.7")
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    valid_until: Mapped[datetime | None] = mapped_column(DateTime)
    source_stardust_ids: Mapped[list] = mapped_column(JSON, nullable=False, server_default="[]")
    strength: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    inferred: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class StardustRelationship(Base):
    __tablename__ = "stardust_relationships"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False)
    source_stardust_id: Mapped[str] = mapped_column(Text, ForeignKey("stardust.id"), nullable=False)
    target_stardust_id: Mapped[str] = mapped_column(Text, ForeignKey("stardust.id"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.7")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(Text)


class EntityBacklink(Base):
    __tablename__ = "entity_backlinks"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    entity_id: Mapped[str] = mapped_column(Text, ForeignKey("entities.id"), nullable=False, index=True)
    stardust_id: Mapped[str] = mapped_column(Text, ForeignKey("stardust.id"), nullable=False, index=True)
    mention_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="explicit")
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    first_mention: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    last_mention: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class GraphPathCache(Base):
    __tablename__ = "graph_path_cache"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    galaxy_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_node_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    source_node_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    target_node_type: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[list] = mapped_column(JSON, nullable=False)
    path_length: Mapped[int] = mapped_column(Integer, nullable=False)
    path_types: Mapped[list] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
