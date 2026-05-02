from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text, Integer, DateTime, JSON, ForeignKey, func
from datetime import datetime
from app.models.galaxy import Base


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False, index=True)
    planet_id: Mapped[str | None] = mapped_column(Text, ForeignKey("planets.id"), index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[int] = mapped_column(Integer, server_default="1")
    profile: Mapped[dict] = mapped_column(JSON, server_default="{}")
    mention_count: Mapped[int] = mapped_column(Integer, server_default="1")
    first_seen: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EntityStardust(Base):
    """Simple entity↔stardust link created during extraction (stardust_service).
    See also: EntityBacklink in brain.py — richer link with mention metadata, used by graph_service."""
    __tablename__ = "entity_stardust"

    entity_id: Mapped[str] = mapped_column(Text, ForeignKey("entities.id"), primary_key=True)
    stardust_id: Mapped[str] = mapped_column(Text, ForeignKey("stardust.id"), primary_key=True)
    relationship_type: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EntityTimeline(Base):
    __tablename__ = "entity_timeline"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    entity_id: Mapped[str] = mapped_column(Text, ForeignKey("entities.id"), nullable=False)
    event_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_content: Mapped[str] = mapped_column(Text, nullable=False)
    source_stardust_id: Mapped[str | None] = mapped_column(Text, ForeignKey("stardust.id"))
