from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text, Integer, DateTime, ForeignKey, func
from datetime import datetime
from app.models.galaxy import Base


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
