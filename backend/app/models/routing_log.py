from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text, Integer, Float, DateTime, ForeignKey, func
from datetime import datetime
from app.models.galaxy import Base


class RoutingLog(Base):
    __tablename__ = "routing_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False, index=True)
    stardust_id: Mapped[str] = mapped_column(Text, ForeignKey("stardust.id"), nullable=False, index=True)
    routed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    caller_suggested_planet: Mapped[str | None] = mapped_column(Text)
    caller_suggested_biome: Mapped[str | None] = mapped_column(Text)
    assigned_planet_id: Mapped[str] = mapped_column(Text, ForeignKey("planets.id"), nullable=False)
    assigned_biome_id: Mapped[str | None] = mapped_column(Text, ForeignKey("biomes.id"))
    routing_method: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text)
    graphify_cluster: Mapped[str | None] = mapped_column(Text)
    corrected_planet_id: Mapped[str | None] = mapped_column(Text, ForeignKey("planets.id"))
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime)
    corrected_by: Mapped[str | None] = mapped_column(Text)
