"""Model Switch Service — handles model transitions while preserving agent continuity."""
import json
import logging
from uuid import uuid4
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.brain import AgentIdentity, AgentSession, ModelSwitchLog, TransitionOrientation, AgentExpertise
from app.services import nebula_service

logger = logging.getLogger(__name__)


class ModelSwitchService:

    async def handle_switch(
        self, identity: AgentIdentity, previous_model: str,
        new_model: str, galaxy_id: str, db: AsyncSession,
    ) -> dict:
        switch_log = ModelSwitchLog(
            id=str(uuid4()), agent_identity_id=identity.id,
            galaxy_id=galaxy_id, previous_model=previous_model,
            new_model=new_model, reason="user_configured",
        )
        db.add(switch_log)

        continuity = self._assess_continuity(previous_model, new_model)
        switch_log.continuity_score = continuity["score"]
        switch_log.compatibility_issues = json.dumps(continuity.get("issues", []))

        brief = await self._generate_transition_brief(identity, previous_model, new_model, galaxy_id, db)
        transition = TransitionOrientation(
            id=str(uuid4()), model_switch_id=switch_log.id,
            agent_identity_id=identity.id,
            from_model=previous_model, to_model=new_model,
            orientation_content=json.dumps(brief), used=0,
        )
        db.add(transition)
        switch_log.transition_orientation_id = transition.id
        await db.commit()

        try:
            await nebula_service.log_event(
                action_type="MODEL_SWITCH", galaxy_id=galaxy_id,
                initiated_by=identity.agent_name,
                payload_before=json.dumps({"model": previous_model}),
                payload_after=json.dumps({"model": new_model, "continuity_score": continuity["score"]}),
            )
        except Exception as e:
            logger.warning(f"Failed to log model switch event: {e}")

        return {"switch_id": switch_log.id, "continuity_score": continuity["score"], "transition_orientation_id": transition.id}

    def _assess_continuity(self, previous: str, new: str) -> dict:
        """Assess continuity between two models. Same family = high continuity."""
        prev_family = self._family(previous)
        new_family = self._family(new)
        if prev_family == new_family:
            return {"score": 0.95, "issues": []}
        # Cross-family switch
        issues = [f"Switching from {prev_family} to {new_family} family"]
        return {"score": 0.7, "issues": issues}

    async def _generate_transition_brief(
        self, identity: AgentIdentity, from_model: str, to_model: str,
        galaxy_id: str, db: AsyncSession,
    ) -> dict:
        # Get last session summary
        last_session = (await db.execute(
            select(AgentSession).where(AgentSession.agent_identity_id == identity.id)
            .order_by(desc(AgentSession.started_at)).limit(1)
        )).scalar_one_or_none()

        # Get top expertise
        expertise = (await db.execute(
            select(AgentExpertise).where(AgentExpertise.agent_identity_id == identity.id)
            .order_by(desc(AgentExpertise.expertise_level)).limit(10)
        )).scalars().all()

        return {
            "transition_notice": (
                f"You are taking over from {from_model}. "
                f"This agent has operated in this Galaxy for "
                f"{identity.total_sessions} sessions since "
                f"{identity.birth_date.strftime('%B %d, %Y') if identity.birth_date else 'unknown'}."
            ),
            "last_session": {
                "model": last_session.model_used if last_session else None,
                "reads": last_session.reads if last_session else 0,
                "writes": last_session.writes if last_session else 0,
                "quality": last_session.session_quality_score if last_session else None,
            } if last_session else None,
            "established_expertise": [
                {"domain": e.domain, "level": e.expertise_level, "evidence": e.evidence_count}
                for e in expertise
            ],
            "operating_note": f"Your context window has been calibrated for {to_model}. The brain is intact. Continue.",
        }

    def _family(self, model: str) -> str:
        m = model.lower()
        for f in ["claude", "gpt", "llama", "gemini", "mistral", "qwen", "deepseek"]:
            if f in m:
                return f
        return "custom"


model_switch_service = ModelSwitchService()
