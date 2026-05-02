from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text, Integer, DateTime, ForeignKey, func
from datetime import datetime
from app.models.galaxy import Base


class Planet(Base):
    __tablename__ = "planets"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(Text, server_default="#6D28D9")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    stardust_count: Mapped[int] = mapped_column(Integer, server_default="0")
    health_status: Mapped[str] = mapped_column(Text, server_default="healthy")
    protocol_override: Mapped[str | None] = mapped_column(Text)
