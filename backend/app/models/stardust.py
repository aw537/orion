from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import Text, Integer, Float, DateTime, ForeignKey, JSON, func
from datetime import datetime
from app.models.galaxy import Base


class Stardust(Base):
    __tablename__ = "stardust"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    biome_id: Mapped[str] = mapped_column(Text, ForeignKey("biomes.id"), nullable=False, index=True)
    planet_id: Mapped[str] = mapped_column(Text, ForeignKey("planets.id"), nullable=False, index=True)
    galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[str] = mapped_column(Text, server_default="contextual")
    gravity: Mapped[str] = mapped_column(Text, server_default="BIOME")
    confidence: Mapped[float] = mapped_column(Float, server_default="0.5")
    valid_from: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    valid_until: Mapped[datetime | None] = mapped_column(DateTime)
    _context_tags: Mapped[list] = mapped_column("context_tags", JSON, server_default="[]")
    contradiction_id: Mapped[str | None] = mapped_column(Text)
    reinforcement_sources: Mapped[int] = mapped_column(Integer, server_default="1")
    source_agent: Mapped[str | None] = mapped_column(Text)
    chroma_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_accessed: Mapped[datetime | None] = mapped_column(DateTime)
    access_count: Mapped[int] = mapped_column(Integer, server_default="0")
    reasoning: Mapped[str | None] = mapped_column(Text)
    supersedes: Mapped[list | None] = mapped_column(JSON)

    @hybrid_property
    def context_tags(self) -> list[str]:
        if self._context_tags is None:
            return []
        if isinstance(self._context_tags, list):
            return self._context_tags
        try:
            import json
            return json.loads(self._context_tags)
        except (ValueError, TypeError):
            return []

    @context_tags.setter
    def context_tags(self, value):
        self._context_tags = value if isinstance(value, list) else ([] if value is None else value)
