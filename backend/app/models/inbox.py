from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text, Integer, DateTime, ForeignKey, func
from datetime import datetime
from app.models.galaxy import Base


class InboxIngestion(Base):
    __tablename__ = "inbox_ingestions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="complete")
    chunks_total: Mapped[int] = mapped_column(Integer, server_default="0")
    chunks_routed: Mapped[int] = mapped_column(Integer, server_default="0")
    results_json: Mapped[str | None] = mapped_column(Text)  # JSON-serialized routing results
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
