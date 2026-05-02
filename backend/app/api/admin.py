"""Admin dashboard REST endpoints — owner/admin only."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Galaxy, Planet, Contradiction
from app.models.user import User
from app.models.brain import AgentIdentity, AgentSession, EntityRelationship
from app.models.profiles import StrengthHistory
from app.auth.dependencies import get_current_user, get_galaxy_for_user

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _require_admin(user: User):
    if user.role not in ("owner", "admin"):
        raise HTTPException(403, "Admin access required")


@router.get("/agents/active")
async def active_agents(user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    _require_admin(user)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    agents = (await db.execute(
        select(AgentIdentity)
        .where(AgentIdentity.galaxy_id == galaxy.id, AgentIdentity.last_active >= cutoff)
        .order_by(desc(AgentIdentity.last_active))
    )).scalars().all()
    return [
        {"id": a.id, "agent_name": a.agent_name, "agent_type": a.agent_type,
         "current_model": a.current_model, "last_active": a.last_active.isoformat() if a.last_active else None,
         "total_sessions": a.total_sessions, "total_reads": a.total_reads, "total_writes": a.total_writes}
        for a in agents
    ]


@router.get("/planets/health")
async def planets_health(user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    _require_admin(user)
    planets = (await db.execute(select(Planet).where(Planet.galaxy_id == galaxy.id))).scalars().all()
    result = []
    for p in planets:
        active_agents = (await db.execute(
            select(func.count()).select_from(AgentSession)
            .where(AgentSession.galaxy_id == galaxy.id, AgentSession.ended_at.is_(None))
        )).scalar() or 0
        result.append({
            "id": p.id, "name": p.name, "stardust_count": p.stardust_count,
            "health_status": p.health_status, "active_agents": active_agents,
        })
    return result


@router.get("/contradictions/summary")
async def contradictions_summary(user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    _require_admin(user)
    rows = (await db.execute(
        select(Contradiction.region, Contradiction.status, func.count().label("cnt"))
        .where(Contradiction.galaxy_id == galaxy.id)
        .group_by(Contradiction.region, Contradiction.status)
    )).all()
    by_status = {}
    for region, status, cnt in rows:
        by_status.setdefault(status, []).append({"region": region, "count": cnt})
    unresolved = sum(r["count"] for r in by_status.get("UNRESOLVED", []))
    return {"unresolved_total": unresolved, "by_status": by_status}


@router.get("/bridges/activity")
async def bridges_activity(user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    _require_admin(user)
    week_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
    # Cross-planet activity = stardust accessed from a different planet context
    # Approximate via entity_relationships spanning different planet entities
    cross_planet = (await db.execute(
        select(func.count()).select_from(EntityRelationship)
        .where(EntityRelationship.galaxy_id == galaxy.id, EntityRelationship.created_at >= week_ago)
    )).scalar() or 0
    return {"cross_planet_relationships_this_week": cross_planet}


@router.get("/sessions/daily")
async def sessions_daily(days: int = 30, user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    _require_admin(user)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    rows = (await db.execute(
        select(
            func.date(AgentSession.started_at).label("date"),
            AgentIdentity.agent_name,
            func.count().label("sessions"),
            func.coalesce(func.sum(AgentSession.reads), 0).label("total_reads"),
            func.coalesce(func.sum(AgentSession.writes), 0).label("total_writes"),
        )
        .join(AgentIdentity, AgentSession.agent_identity_id == AgentIdentity.id)
        .where(AgentSession.galaxy_id == galaxy.id, AgentSession.started_at >= cutoff)
        .group_by(func.date(AgentSession.started_at), AgentIdentity.agent_name)
        .order_by(func.date(AgentSession.started_at))
    )).all()
    by_date: dict[str, dict] = {}
    for date, agent_name, sessions, reads, writes in rows:
        d = str(date)
        if d not in by_date:
            by_date[d] = {"date": d, "sessions": 0, "total_reads": 0, "total_writes": 0, "agents": []}
        by_date[d]["sessions"] += sessions
        by_date[d]["total_reads"] += reads
        by_date[d]["total_writes"] += writes
        by_date[d]["agents"].append({"name": agent_name, "sessions": sessions})
    return list(by_date.values())


@router.get("/strength/history")
async def strength_history(days: int = 90, user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    _require_admin(user)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    rows = (await db.execute(
        select(StrengthHistory)
        .where(StrengthHistory.galaxy_id == galaxy.id, StrengthHistory.computed_at >= cutoff)
        .order_by(StrengthHistory.computed_at)
    )).scalars().all()
    return [
        {"computed_at": r.computed_at.isoformat(), "score": r.score}
        for r in rows
    ]
