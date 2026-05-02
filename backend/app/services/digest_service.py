"""Weekly Digest — generates and delivers Galaxy activity summaries."""
import json
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models import Galaxy, Planet, Stardust, Entity, Contradiction
from app.models.user import User
from app.models.nebula import InteractionLog
from app.models.brain import AgentSession

logger = logging.getLogger(__name__)


async def generate_digest(galaxy_id: str, db: AsyncSession) -> dict:
    """Generate a weekly activity digest for a Galaxy."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    week_ago = now - timedelta(days=7)

    # Activity counts
    events_this_week = (await db.execute(
        select(func.count()).select_from(InteractionLog)
        .where(InteractionLog.galaxy_id == galaxy_id, InteractionLog.timestamp >= week_ago)
    )).scalar() or 0

    new_stardust = (await db.execute(
        select(func.count()).select_from(Stardust)
        .where(Stardust.galaxy_id == galaxy_id, Stardust.created_at >= week_ago)
    )).scalar() or 0

    new_entities = (await db.execute(
        select(func.count()).select_from(Entity)
        .where(Entity.galaxy_id == galaxy_id, Entity.first_seen >= week_ago)
    )).scalar() or 0

    new_contradictions = (await db.execute(
        select(func.count()).select_from(Contradiction)
        .where(Contradiction.galaxy_id == galaxy_id, Contradiction.detected_at >= week_ago)
    )).scalar() or 0

    resolved_contradictions = (await db.execute(
        select(func.count()).select_from(Contradiction)
        .where(Contradiction.galaxy_id == galaxy_id, Contradiction.resolved_at >= week_ago)
    )).scalar() or 0

    sessions_this_week = (await db.execute(
        select(func.count()).select_from(AgentSession)
        .where(AgentSession.galaxy_id == galaxy_id, AgentSession.started_at >= week_ago)
    )).scalar() or 0

    # Galaxy strength
    galaxy = await db.get(Galaxy, galaxy_id)
    strength = galaxy.strength_score if galaxy else 0

    # Top planets by activity
    planet_activity = (await db.execute(
        select(InteractionLog.planet_id, func.count().label("cnt"))
        .where(InteractionLog.galaxy_id == galaxy_id, InteractionLog.timestamp >= week_ago, InteractionLog.planet_id.isnot(None))
        .group_by(InteractionLog.planet_id)
        .order_by(func.count().desc())
        .limit(5)
    )).all()

    planet_names = {}
    for pid, _ in planet_activity:
        if pid:
            p = await db.get(Planet, pid)
            if p:
                planet_names[pid] = p.name

    return {
        "galaxy_id": galaxy_id,
        "galaxy_name": galaxy.name if galaxy else "Unknown",
        "period_start": week_ago.isoformat(),
        "period_end": now.isoformat(),
        "strength_score": strength,
        "events_this_week": events_this_week,
        "new_stardust": new_stardust,
        "new_entities": new_entities,
        "new_contradictions": new_contradictions,
        "resolved_contradictions": resolved_contradictions,
        "agent_sessions": sessions_this_week,
        "top_planets": [
            {"planet_id": pid, "planet_name": planet_names.get(pid, pid), "events": cnt}
            for pid, cnt in planet_activity
        ],
    }


async def send_digest_to_users(galaxy_id: str) -> list[str]:
    """Generate and deliver digest to all users with digest enabled.

    Returns list of user emails that received the digest.
    For MVP: logs the digest. Actual SMTP integration is deployment-specific.
    """
    delivered = []
    async with async_session() as db:
        digest = await generate_digest(galaxy_id, db)

        users = (await db.execute(
            select(User).where(User.galaxy_id == galaxy_id, User.is_active == True)
        )).scalars().all()

        for user in users:
            prefs = json.loads(user.preferences) if user.preferences else {}
            if prefs.get("digest_enabled", True):  # Default: enabled
                logger.info(
                    f"Weekly digest for {user.email}: "
                    f"{digest['new_stardust']} new records, "
                    f"{digest['agent_sessions']} sessions, "
                    f"strength {digest['strength_score']:.1f}"
                )
                delivered.append(user.email)

    return delivered
