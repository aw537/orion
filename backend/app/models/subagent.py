from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text, Integer, Float, DateTime, ForeignKey, func
from datetime import datetime
from app.models.galaxy import Base


class Subagent(Base):
    __tablename__ = "subagents"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False)
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(Text)
    planet_scope: Mapped[str | None] = mapped_column(Text)
    biome_scope: Mapped[str] = mapped_column(Text, server_default='["*"]')
    trust_level: Mapped[int] = mapped_column(Integer, server_default="1")
    write_authority: Mapped[str] = mapped_column(Text, server_default="CACHE_ONLY")
    session_id: Mapped[str | None] = mapped_column(Text)
    registered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_active: Mapped[datetime | None] = mapped_column(DateTime)
    total_reads: Mapped[int] = mapped_column(Integer, server_default="0")
    total_writes: Mapped[int] = mapped_column(Integer, server_default="0")
    contradiction_rate: Mapped[float] = mapped_column(Float, server_default="0.0")
    agent_identity_id: Mapped[str | None] = mapped_column(Text)


class AuditRun(Base):
    __tablename__ = "audit_runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    run_by: Mapped[str] = mapped_column(Text, server_default="audit_ai")
    records_reviewed: Mapped[int] = mapped_column(Integer, server_default="0")
    duplicates_merged: Mapped[int] = mapped_column(Integer, server_default="0")
    contradictions_found: Mapped[int] = mapped_column(Integer, server_default="0")
    contradictions_classified: Mapped[int] = mapped_column(Integer, server_default="0")
    promotions_made: Mapped[int] = mapped_column(Integer, server_default="0")
    confidence_decays: Mapped[int] = mapped_column(Integer, server_default="0")
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str | None] = mapped_column(Text)


class SchemaVersion(Base):
    __tablename__ = "schema_versions"

    version_id: Mapped[str] = mapped_column(Text, primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    checksum: Mapped[str] = mapped_column(Text, nullable=False)
