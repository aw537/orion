from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Text, Integer, Float, DateTime, ForeignKey, JSON, func
from datetime import datetime


class Base(DeclarativeBase):
    pass


class Galaxy(Base):
    __tablename__ = "galaxies"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    owner_agent: Mapped[str | None] = mapped_column(Text)
    strength_score: Mapped[float] = mapped_column(Float, server_default="0.0")
    total_nodes: Mapped[int] = mapped_column(Integer, server_default="1")
    schema_version: Mapped[str] = mapped_column(Text, server_default="001")


class SunSection(Base):
    __tablename__ = "sun_sections"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False)
    section_key: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    schema_version: Mapped[str | None] = mapped_column(Text, server_default="v0.5")
