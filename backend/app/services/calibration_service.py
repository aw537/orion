"""Calibration Service — teaches the brain what was useful each session."""
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.stardust import Stardust
from app.models.brain import AgentIdentity, SessionCalibration
from app.services import nebula_service

logger = logging.getLogger(__name__)


class CalibrationService:

    async def process_calibration(
        self, session_id: str, agent_identity_id: str, galaxy_id: str,
        records_used: list[str], records_retrieved_unused: list[str],
        knowledge_gaps: list[str], session_outcome: str | None,
        knowledge_quality_score: float | None, db: AsyncSession,
    ) -> dict:
        boosted = 0
        for rid in records_used:
            record = await db.get(Stardust, rid)
            if record:
                old = record.confidence
                record.confidence = min(1.0, record.confidence + 0.02)
                record.access_count += 1
                record.last_accessed = datetime.now(timezone.utc).replace(tzinfo=None)
                boosted += 1
                try:
                    await nebula_service.log_event(
                        action_type="CONFIDENCE_BOOST", galaxy_id=galaxy_id,
                        record_id=rid, confidence_delta=record.confidence - old,
                        initiated_by="calibration", db=db,
                    )
                except Exception:
                    pass

        decayed = 0
        for rid in records_retrieved_unused:
            record = await db.get(Stardust, rid)
            if record:
                record.confidence = max(0.0, record.confidence - 0.005)
                decayed += 1

        cal = SessionCalibration(
            id=str(uuid4()), session_id=session_id,
            agent_identity_id=agent_identity_id, galaxy_id=galaxy_id,
            records_used=records_used,
            records_retrieved_unused=records_retrieved_unused,
            knowledge_gaps=knowledge_gaps,
            session_outcome=session_outcome,
            knowledge_quality_score=knowledge_quality_score,
        )
        db.add(cal)

        # EMA update of agent quality score
        identity = await db.get(AgentIdentity, agent_identity_id)
        if identity and knowledge_quality_score is not None:
            alpha = 0.1
            if identity.retrieval_quality_score == 0.0:
                identity.retrieval_quality_score = knowledge_quality_score
            else:
                identity.retrieval_quality_score = (
                    alpha * knowledge_quality_score + (1 - alpha) * identity.retrieval_quality_score
                )

        await db.commit()

        try:
            await nebula_service.log_event(
                action_type="SESSION_CALIBRATION", galaxy_id=galaxy_id,
                initiated_by="calibration", session_id=session_id,
            )
        except Exception:
            pass

        return {
            "calibration_id": cal.id,
            "records_boosted": boosted,
            "records_decayed": decayed,
            "gaps_logged": len(knowledge_gaps),
        }


calibration_service = CalibrationService()
