"""Orientation Service — builds the complete cognitive state package for session start."""
import json
import logging
from uuid import uuid4
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Planet, ModelProfile
from app.models.brain import AgentIdentity, TransitionOrientation
from app.services import sun_service, context_service
from app.services.agent_identity_service import agent_identity_service

logger = logging.getLogger(__name__)


class OrientationService:

    async def build_orientation(
        self, agent_identity: AgentIdentity, galaxy_id: str,
        active_planet: str | None, active_biome: str | None,
        max_tokens: int | None, db: AsyncSession,
    ) -> dict:
        """Builds the complete cognitive state package for session start."""
        # Resolve model profile for token budget
        profile = await self._get_model_profile(agent_identity.current_model, db)
        budget = max_tokens or (profile.optimal_context_tokens if profile else 4000)

        sun = await sun_service.get_full_sun(galaxy_id, db)

        # Layer 1: Agent identity
        expertise = await agent_identity_service.get_expertise(agent_identity.id, db)
        identity_layer = {
            "agent_name": agent_identity.agent_name,
            "agent_type": agent_identity.agent_type,
            "current_model": agent_identity.current_model,
            "model_family": agent_identity.model_family,
            "total_sessions": agent_identity.total_sessions,
            "total_reads": agent_identity.total_reads,
            "total_writes": agent_identity.total_writes,
            "birth_date": agent_identity.birth_date.isoformat() if agent_identity.birth_date else None,
            "expertise": expertise,
            "retrieval_quality_score": agent_identity.retrieval_quality_score,
            "calibration_score": agent_identity.calibration_score,
        }

        # Layer 2: Galaxy identity (from Sun)
        galaxy_layer = {
            "identity": sun.get("identity", {}),
            "values": sun.get("values", {}),
        }

        # Layer 3: Working context
        context_layer = sun.get("working_context", {})

        # Layer 4: Synthesized knowledge state
        knowledge_layer = await self._build_knowledge_state(
            galaxy_id, active_planet, active_biome, budget, db,
        )

        # Layer 5: Operating protocol
        protocol = sun.get("agent_protocol", {})
        # Merge Planet-level override if present
        if active_planet:
            planet = (await db.execute(
                select(Planet).where(Planet.galaxy_id == galaxy_id, Planet.name == active_planet)
            )).scalar_one_or_none()
            if planet and planet.protocol_override:
                try:
                    override = json.loads(planet.protocol_override)
                    protocol = {**protocol, **override}
                except (json.JSONDecodeError, TypeError):
                    pass
        protocol_layer = {
            "write_rules": protocol.get("write_rules", []),
            "read_rules": protocol.get("read_rules", []),
            "uncertainty_handling": protocol.get("uncertainty_handling", ""),
            "session_start_instruction": protocol.get("session_start_instruction", ""),
            "session_end_instruction": protocol.get("session_end_instruction", ""),
        }

        # Transition brief if model switched
        transition = await self._get_pending_transition(agent_identity.id, db)
        if transition:
            transition.used = 1
            await db.commit()

        # Start session
        session = await agent_identity_service.start_session(agent_identity, galaxy_id, db)

        # Record galaxy strength at session start for delta tracking (H1.1)
        try:
            from app.services.galaxy_service import get_galaxy_strength
            strength = await get_galaxy_strength(galaxy_id, db)
            session.galaxy_strength_at_start = strength.get("score", 0.0)
            await db.commit()
        except Exception:
            pass

        return {
            "orientation_id": str(uuid4()),
            "session_id": session.id,
            "agent_identity": identity_layer,
            "galaxy_identity": galaxy_layer,
            "current_context": context_layer,
            "knowledge_state": knowledge_layer,
            "operating_protocol": protocol_layer,
            "model_calibration": {
                "model": agent_identity.current_model,
                "token_budget": budget,
                "format_preference": profile.format_preference if profile else "markdown",
                "tool_calling": profile.tool_calling if profile else "prompted",
            },
            "transition_brief": json.loads(transition.orientation_content) if transition else None,
            "orion_status_line": self._build_status_line(knowledge_layer, galaxy_id, db),
        }

    def _build_status_line(self, knowledge_layer: dict, galaxy_id: str, db) -> str:
        from app.services.session_summary_service import build_status_line
        records = knowledge_layer.get("records_count", knowledge_layer.get("total_records", 0))
        biome = knowledge_layer.get("active_biome", knowledge_layer.get("biome_name", "Galaxy"))
        strength = knowledge_layer.get("galaxy_strength", 0)
        return build_status_line(records, biome, strength)

    async def _build_knowledge_state(
        self, galaxy_id: str, active_planet: str | None,
        active_biome: str | None, budget: int, db: AsyncSession,
    ) -> dict:
        """Build a synthesized knowledge state, not raw records."""
        bundle = await context_service.build_context(
            galaxy_id, planet_name=active_planet, biome_name=active_biome,
            max_tokens=min(budget, 4000),
        )
        return bundle.model_dump(mode="json")

    async def _get_model_profile(self, model: str, db: AsyncSession) -> ModelProfile | None:
        result = await db.execute(select(ModelProfile).where(ModelProfile.model_id == model))
        profile = result.scalar_one_or_none()
        if not profile:
            result = await db.execute(select(ModelProfile).where(ModelProfile.model_id == "__unknown__"))
            profile = result.scalar_one_or_none()
        return profile

    async def _get_pending_transition(self, agent_identity_id: str, db: AsyncSession) -> TransitionOrientation | None:
        result = await db.execute(
            select(TransitionOrientation)
            .where(TransitionOrientation.agent_identity_id == agent_identity_id, TransitionOrientation.used == 0)
            .order_by(desc(TransitionOrientation.generated_at))
            .limit(1)
        )
        return result.scalar_one_or_none()


orientation_service = OrientationService()
