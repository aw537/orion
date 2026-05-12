from sqlalchemy.orm import Mapped, mapped_column
import sqlalchemy as sa
from sqlalchemy import Text, Integer, Float, DateTime, Boolean, func
from datetime import datetime
from app.models.galaxy import Base


class StrengthHistory(Base):
    __tablename__ = "strength_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # No FK on galaxy_id: append-only analytics log; FK cascade would silently
    # delete historical scores if a galaxy is removed. Accept orphaned rows instead.
    galaxy_id: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    volume_score: Mapped[float] = mapped_column(Float, nullable=False)
    density_score: Mapped[float] = mapped_column(Float, nullable=False)
    health_score: Mapped[float] = mapped_column(Float, nullable=False)
    diversity_score: Mapped[float] = mapped_column(Float, nullable=False)
    coverage_score: Mapped[float] = mapped_column(Float, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ModelProfile(Base):
    __tablename__ = "model_profiles"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    model_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    context_window_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    optimal_context_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    format_preference: Mapped[str] = mapped_column(Text, server_default="structured_json")
    tool_calling: Mapped[str] = mapped_column(Text, server_default="native")
    is_builtin: Mapped[bool] = mapped_column(Boolean, server_default=sa.true())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
