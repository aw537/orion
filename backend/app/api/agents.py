"""Agent identity and brain REST API endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Galaxy
from app.models.brain import AgentIdentity, AgentSession, ModelSwitchLog
from app.auth.dependencies import get_galaxy_for_user

router = APIRouter(prefix="/api/v1", tags=["agents"])


@router.get("/agents")
async def list_agents(galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    agents = (await db.execute(
        select(AgentIdentity).where(AgentIdentity.galaxy_id == galaxy.id)
        .order_by(desc(AgentIdentity.last_active))
    )).scalars().all()
    return [
        {"id": a.id, "agent_name": a.agent_name, "agent_type": a.agent_type,
         "current_model": a.current_model, "model_family": a.model_family,
         "total_sessions": a.total_sessions, "total_reads": a.total_reads,
         "total_writes": a.total_writes, "retrieval_quality_score": a.retrieval_quality_score,
         "last_active": a.last_active.isoformat() if a.last_active else None,
         "birth_date": a.birth_date.isoformat() if a.birth_date else None}
        for a in agents
    ]


@router.get("/agents/{agent_name}")
async def get_agent(agent_name: str, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    agent = (await db.execute(
        select(AgentIdentity).where(AgentIdentity.galaxy_id == galaxy.id, AgentIdentity.agent_name == agent_name)
    )).scalar_one_or_none()
    if not agent:
        return {"error": f"Agent '{agent_name}' not found"}
    return {
        "id": agent.id, "agent_name": agent.agent_name, "agent_type": agent.agent_type,
        "current_model": agent.current_model, "model_family": agent.model_family,
        "total_sessions": agent.total_sessions, "total_reads": agent.total_reads,
        "total_writes": agent.total_writes,
        "retrieval_quality_score": agent.retrieval_quality_score,
        "calibration_score": agent.calibration_score,
        "contradiction_rate": agent.contradiction_rate,
        "last_active": agent.last_active.isoformat() if agent.last_active else None,
        "birth_date": agent.birth_date.isoformat() if agent.birth_date else None,
    }


@router.get("/agents/{agent_name}/expertise")
async def get_agent_expertise(agent_name: str, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    from app.services.agent_identity_service import agent_identity_service
    agent = (await db.execute(
        select(AgentIdentity).where(AgentIdentity.galaxy_id == galaxy.id, AgentIdentity.agent_name == agent_name)
    )).scalar_one_or_none()
    if not agent:
        return {"error": f"Agent '{agent_name}' not found"}
    return await agent_identity_service.get_expertise(agent.id, db, limit=50)


@router.get("/agents/{agent_name}/sessions")
async def get_agent_sessions(agent_name: str, limit: int = Query(20, le=100), galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    agent = (await db.execute(
        select(AgentIdentity).where(AgentIdentity.galaxy_id == galaxy.id, AgentIdentity.agent_name == agent_name)
    )).scalar_one_or_none()
    if not agent:
        return {"error": f"Agent '{agent_name}' not found"}
    sessions = (await db.execute(
        select(AgentSession).where(AgentSession.agent_identity_id == agent.id)
        .order_by(desc(AgentSession.started_at)).limit(limit)
    )).scalars().all()
    return [
        {"id": s.id, "model_used": s.model_used,
         "started_at": s.started_at.isoformat() if s.started_at else None,
         "ended_at": s.ended_at.isoformat() if s.ended_at else None,
         "reads": s.reads, "writes": s.writes,
         "session_quality_score": s.session_quality_score,
         "model_switch_from": s.model_switch_from}
        for s in sessions
    ]


@router.get("/agents/{agent_name}/health")
async def get_agent_health(agent_name: str, galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    from app.services.brain_health_service import brain_health_service
    agent = (await db.execute(
        select(AgentIdentity).where(AgentIdentity.galaxy_id == galaxy.id, AgentIdentity.agent_name == agent_name)
    )).scalar_one_or_none()
    if not agent:
        return {"error": f"Agent '{agent_name}' not found"}
    return await brain_health_service.get_brain_health(agent, galaxy.id, db)


@router.get("/model-switches")
async def list_model_switches(limit: int = Query(20, le=100), galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    switches = (await db.execute(
        select(ModelSwitchLog).where(ModelSwitchLog.galaxy_id == galaxy.id)
        .order_by(desc(ModelSwitchLog.switched_at)).limit(limit)
    )).scalars().all()
    return [
        {"id": s.id, "agent_identity_id": s.agent_identity_id,
         "previous_model": s.previous_model, "new_model": s.new_model,
         "switched_at": s.switched_at.isoformat() if s.switched_at else None,
         "continuity_score": s.continuity_score, "reason": s.reason}
        for s in switches
    ]


@router.get("/model-switches/latest")
async def latest_model_switches(galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    agents = (await db.execute(
        select(AgentIdentity).where(AgentIdentity.galaxy_id == galaxy.id)
    )).scalars().all()
    result = []
    for agent in agents:
        switch = (await db.execute(
            select(ModelSwitchLog).where(ModelSwitchLog.agent_identity_id == agent.id)
            .order_by(desc(ModelSwitchLog.switched_at)).limit(1)
        )).scalar_one_or_none()
        if switch:
            result.append({
                "agent_name": agent.agent_name,
                "previous_model": switch.previous_model, "new_model": switch.new_model,
                "switched_at": switch.switched_at.isoformat() if switch.switched_at else None,
                "continuity_score": switch.continuity_score,
            })
    return result
