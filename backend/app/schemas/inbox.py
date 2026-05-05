from pydantic import BaseModel
from datetime import datetime


class InboxUploadResponse(BaseModel):
    ingestion_id: str
    filename: str
    status: str  # "processing" | "complete" | "failed"
    chunks_total: int
    chunks_routed: int
    results: list["InboxRoutingResult"]


class InboxRoutingResult(BaseModel):
    chunk_preview: str
    target_planet_id: str
    target_planet_name: str
    target_biome_id: str | None
    target_biome_name: str | None
    confidence: float
    method: str


class InboxHistoryItem(BaseModel):
    ingestion_id: str
    filename: str
    status: str
    chunks_total: int
    chunks_routed: int
    created_at: datetime


class InboxHistoryResponse(BaseModel):
    items: list[InboxHistoryItem]
    total: int
