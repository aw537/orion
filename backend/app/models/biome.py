from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text, Integer, Boolean, DateTime, ForeignKey, false, func
from datetime import datetime
from app.models.galaxy import Base


class Biome(Base):
    __tablename__ = "biomes"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    planet_id: Mapped[str] = mapped_column(Text, ForeignKey("planets.id"), nullable=False)
    galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    lifecycle_state: Mapped[str] = mapped_column(Text, server_default="SEED")
    is_inbox: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime)
    stardust_count: Mapped[int] = mapped_column(Integer, server_default="0")
    cache_ttl_seconds: Mapped[int] = mapped_column(Integer, server_default="14400")
