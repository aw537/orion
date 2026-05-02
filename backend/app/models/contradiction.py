from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text, Integer, DateTime, ForeignKey, func
from datetime import datetime
from app.models.galaxy import Base


class Contradiction(Base):
    __tablename__ = "contradictions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False)
    region: Mapped[str | None] = mapped_column(Text)
    # No FK on record_a_id/record_b_id: stardust_service inserts Contradiction
    # before the referenced Stardust row in the same transaction.
    record_a_id: Mapped[str | None] = mapped_column(Text)
    record_b_id: Mapped[str | None] = mapped_column(Text)
    conflict_type: Mapped[str] = mapped_column(Text, nullable=False)
    context_a: Mapped[str | None] = mapped_column(Text)
    context_b: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="UNRESOLVED")
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    detected_by: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved_by: Mapped[str | None] = mapped_column(Text)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    human_reviewed: Mapped[int] = mapped_column(Integer, server_default="0")
