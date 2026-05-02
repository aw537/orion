from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text, Integer, Float, DateTime, ForeignKey, func
from datetime import datetime
from app.models.galaxy import Base


# NOTE: This model file is named nebula.py but contains InteractionLog, not a "Nebula" model.
# The "Nebula" concept in Orion refers to the interaction/event log system.
# Renaming would break migrations and all importers — documented here for clarity.
# See also: STYLE-001 in BUGS.md.


class InteractionLog(Base):
    __tablename__ = "interaction_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False)
    session_id: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    initiated_by: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    planet_id: Mapped[str | None] = mapped_column(Text)
    biome_id: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    record_id: Mapped[str | None] = mapped_column(Text)
    payload_before: Mapped[str | None] = mapped_column(Text)
    payload_after: Mapped[str | None] = mapped_column(Text)
    confidence_delta: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    cache_hit: Mapped[int | None] = mapped_column(Integer)
    personal_data: Mapped[int] = mapped_column(Integer, server_default="0")
