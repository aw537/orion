from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text, Integer, Float, DateTime, Boolean, ForeignKey, false, func
from datetime import datetime
from app.models.galaxy import Base


class MergeProposal(Base):
    __tablename__ = "merge_proposals"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False, index=True)
    target_galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False, index=True)
    proposed_by: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    accepted_by: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="proposed")
    merged_sun: Mapped[str | None] = mapped_column(Text)
    entity_mappings_count: Mapped[int] = mapped_column(Integer, server_default="0")
    reconciliation_done: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    bridges_created: Mapped[int] = mapped_column(Integer, server_default="0")
    bridging_done: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    rejection_reason: Mapped[str | None] = mapped_column(Text)


class EntityMergeMapping(Base):
    __tablename__ = "entity_merge_mappings"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    proposal_id: Mapped[str] = mapped_column(Text, ForeignKey("merge_proposals.id"), nullable=False, index=True)
    source_entity_id: Mapped[str] = mapped_column(Text, ForeignKey("entities.id"), nullable=False)
    target_entity_id: Mapped[str] = mapped_column(Text, ForeignKey("entities.id"), nullable=False)
    match_type: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default="1.0")
    merged: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
