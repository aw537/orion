"""Agent Identity Service — makes agents persistent across sessions and model changes."""
import logging
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session
from app.models.brain import AgentIdentity, AgentSession, AgentExpertise

logger = logging.getLogger(__name__)


class AgentIdentityService:

    async def get_or_create_identity(
        self, galaxy_id: str, agent_name: str, model: str,
        agent_type: str = "GENERAL", db: AsyncSession | None = None,
    ) -> AgentIdentity:
        async def _do(session: AsyncSession) -> AgentIdentity:
            result = await session.execute(
                select(AgentIdentity)
                .where(AgentIdentity.galaxy_id == galaxy_id, AgentIdentity.agent_name == agent_name)
            )
            identity = result.scalar_one_or_none()

            if identity:
                identity.current_model = model
                identity.model_family = self._infer_family(model)
                identity.last_active = datetime.now(timezone.utc).replace(tzinfo=None)
                await session.commit()
                return identity

            new_identity = AgentIdentity(
                id=str(uuid4()), galaxy_id=galaxy_id, agent_name=agent_name,
                agent_type=agent_type, model_family=self._infer_family(model),
                current_model=model, birth_date=datetime.now(timezone.utc).replace(tzinfo=None),
                expertise_profile={},
            )
            session.add(new_identity)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                # Another concurrent call created it — fetch and update
                result = await session.execute(
                    select(AgentIdentity)
                    .where(AgentIdentity.galaxy_id == galaxy_id, AgentIdentity.agent_name == agent_name)
                )
                identity = result.scalar_one()
                identity.current_model = model
                identity.model_family = self._infer_family(model)
                identity.last_active = datetime.now(timezone.utc).replace(tzinfo=None)
                await session.commit()
                return identity
            return new_identity

        if db:
            return await _do(db)
        async with async_session() as session:
            return await _do(session)

    async def start_session(
        self, identity: AgentIdentity, galaxy_id: str, db: AsyncSession,
    ) -> AgentSession:
        session = AgentSession(
            id=str(uuid4()), agent_identity_id=identity.id,
            galaxy_id=galaxy_id, model_used=identity.current_model,
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(session)
        identity.total_sessions += 1
        await db.commit()
        return session

    async def end_session(self, session_id: str, db: AsyncSession) -> None:
        session = await db.get(AgentSession, session_id)
        if not session:
            return
        session.ended_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()

    async def update_expertise(
        self, identity_id: str, domains: list[str], db: AsyncSession,
    ) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for domain in domains:
            result = await db.execute(
                select(AgentExpertise)
                .where(AgentExpertise.agent_identity_id == identity_id, AgentExpertise.domain == domain)
            )
            exp = result.scalar_one_or_none()
            if exp:
                # Compute recency BEFORE updating last_demonstrated
                recency = 0.1 if exp.last_demonstrated and (now - exp.last_demonstrated).days <= 7 else 0
                exp.evidence_count += 1
                exp.last_demonstrated = now
                exp.expertise_level = min(1.0, exp.evidence_count * 0.05 + recency)
            else:
                db.add(AgentExpertise(
                    id=str(uuid4()), agent_identity_id=identity_id,
                    domain=domain, expertise_level=0.05,
                    evidence_count=1, last_demonstrated=now,
                ))
        await db.commit()

    async def get_expertise(self, identity_id: str, db: AsyncSession, limit: int = 10) -> list[dict]:
        result = await db.execute(
            select(AgentExpertise)
            .where(AgentExpertise.agent_identity_id == identity_id)
            .order_by(AgentExpertise.expertise_level.desc())
            .limit(limit)
        )
        return [
            {"domain": e.domain, "level": e.expertise_level, "evidence_count": e.evidence_count,
             "last_demonstrated": e.last_demonstrated.isoformat() if e.last_demonstrated else None}
            for e in result.scalars().all()
        ]

    async def get_recent_sessions(self, identity_id: str, db: AsyncSession, limit: int = 5) -> list[AgentSession]:
        result = await db.execute(
            select(AgentSession)
            .where(AgentSession.agent_identity_id == identity_id)
            .order_by(AgentSession.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    def _infer_family(self, model: str) -> str:
        m = model.lower()
        matches = [f for f in ["claude", "gpt", "llama", "gemini", "mistral", "qwen", "deepseek"] if f in m]
        if len(matches) > 1:
            logger.warning("Ambiguous model name '%s' matches multiple families: %s — using first match", model, matches)
        if matches:
            return matches[0]
        return "custom"


agent_identity_service = AgentIdentityService()
