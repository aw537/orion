"""Brain Health Service — assesses cognitive health of an agent's brain."""
import json
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.stardust import Stardust
from app.models.brain import AgentIdentity, SessionCalibration
from app.services.agent_identity_service import agent_identity_service

logger = logging.getLogger(__name__)


class BrainHealthService:

    async def get_brain_health(
        self, agent_identity: AgentIdentity, galaxy_id: str, db: AsyncSession,
    ) -> dict:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        thirty_days_ago = now - timedelta(days=30)

        total = (await db.execute(
            select(func.count()).select_from(Stardust).where(Stardust.galaxy_id == galaxy_id)
        )).scalar() or 0

        recent = (await db.execute(
            select(func.count()).select_from(Stardust)
            .where(Stardust.galaxy_id == galaxy_id, Stardust.created_at >= thirty_days_ago)
        )).scalar() or 0

        freshness = recent / max(total, 1)

        # Stale beliefs: high confidence but not accessed in 30 days (or never accessed)
        stale = (await db.execute(
            select(Stardust.id, Stardust.content)
            .where(
                Stardust.galaxy_id == galaxy_id,
                Stardust.confidence >= 0.7,
                or_(Stardust.last_accessed < thirty_days_ago, Stardust.last_accessed.is_(None)),
            )
            .limit(5)
        )).all()
        stale_beliefs = [{"id": s.id, "content": s.content[:100]} for s in stale]

        # Coverage gaps from calibration
        gaps = []
        cal_rows = (await db.execute(
            select(SessionCalibration.knowledge_gaps)
            .where(SessionCalibration.agent_identity_id == agent_identity.id)
            .order_by(SessionCalibration.submitted_at.desc())
            .limit(5)
        )).scalars().all()
        for row in cal_rows:
            if isinstance(row, list):
                gaps.extend(row)
            elif row:
                try:
                    gaps.extend(json.loads(row))
                except (json.JSONDecodeError, TypeError):
                    pass
        # Deduplicate
        gaps = list(dict.fromkeys(gaps))[:5]

        expertise = await agent_identity_service.get_expertise(agent_identity.id, db)

        health_score = (
            freshness * 0.30
            + (1 - min(1.0, len(gaps) / 10)) * 0.30
            + (1 - min(1.0, len(stale_beliefs) / 10)) * 0.20
            + agent_identity.retrieval_quality_score * 0.20
        )

        recommendations = []
        if freshness < 0.3:
            recommendations.append("Knowledge is getting stale. Write new observations to active biomes.")
        if len(gaps) > 3:
            recommendations.append(f"Multiple knowledge gaps detected: {', '.join(gaps[:3])}. Consider enriching these areas.")
        if len(stale_beliefs) > 3:
            recommendations.append("Several high-confidence beliefs haven't been accessed recently. Review and update or supersede.")
        if agent_identity.retrieval_quality_score < 0.5:
            recommendations.append("Retrieval quality is low. Use brain.calibrate more consistently.")

        return {
            "overall_health": round(health_score, 2),
            "knowledge_freshness": round(freshness, 2),
            "total_knowledge_items": total,
            "coverage_gaps": gaps,
            "stale_beliefs": stale_beliefs,
            "expertise_summary": expertise,
            "recommended_enrichment": recommendations,
            "agent_sessions": agent_identity.total_sessions,
            "current_model": agent_identity.current_model,
            "brain_age_days": (now - (agent_identity.birth_date.replace(tzinfo=None) if agent_identity.birth_date and agent_identity.birth_date.tzinfo else agent_identity.birth_date)).days if agent_identity.birth_date else 0,
        }


brain_health_service = BrainHealthService()
