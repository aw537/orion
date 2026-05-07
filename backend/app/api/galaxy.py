from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Galaxy, SunSection, Planet, Biome, Stardust, Entity, Contradiction
from app.models.user import User, GalaxyInvite
from app.auth.dependencies import get_current_user, get_galaxy_for_user
from app.auth.service import hash_password, create_session
from app.schemas.galaxy import GalaxyResponse, PlanetSummary, SunSectionResponse, GalaxyStatusResponse

router = APIRouter(prefix="/api/v1/galaxy", tags=["galaxy"])


@router.get("", response_model=GalaxyResponse | None)
async def get_galaxy(galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    planets = (await db.execute(select(Planet).where(Planet.galaxy_id == galaxy.id))).scalars().all()
    planet_summaries = []
    for p in planets:
        biomes = (await db.execute(
            select(Biome.name).where(Biome.planet_id == p.id, Biome.lifecycle_state.in_(["SEED", "ACTIVE", "MATURE"]))
        )).scalars().all()
        planet_summaries.append(PlanetSummary(id=p.id, name=p.name, stardust_count=p.stardust_count, health_status=p.health_status, active_biomes=list(biomes), color=p.color or "#6D28D9", planet_type=p.planet_type or "standard"))
    return GalaxyResponse(id=galaxy.id, name=galaxy.name, created_at=galaxy.created_at, owner_agent=galaxy.owner_agent, strength_score=galaxy.strength_score, total_nodes=galaxy.total_nodes, schema_version=galaxy.schema_version, planets=planet_summaries)


@router.get("/strength")
async def get_strength(galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    from app.services import galaxy_service
    return await galaxy_service.get_galaxy_strength(galaxy.id, db)


@router.get("/sun", response_model=list[SunSectionResponse])
async def get_sun(galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    sections = (await db.execute(select(SunSection).where(SunSection.galaxy_id == galaxy.id))).scalars().all()
    return [SunSectionResponse(id=s.id, section_key=s.section_key, content=s.content, version=s.version, updated_at=s.updated_at) for s in sections]


@router.get("/status", response_model=GalaxyStatusResponse)
async def get_status(galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    planets = (await db.execute(select(Planet).where(Planet.galaxy_id == galaxy.id))).scalars().all()
    total_stardust = (await db.execute(select(func.count()).select_from(Stardust).where(Stardust.galaxy_id == galaxy.id))).scalar() or 0
    total_entities = (await db.execute(select(func.count()).select_from(Entity).where(Entity.galaxy_id == galaxy.id))).scalar() or 0
    unresolved = (await db.execute(select(func.count()).select_from(Contradiction).where(Contradiction.galaxy_id == galaxy.id, Contradiction.status == "UNRESOLVED"))).scalar() or 0
    planet_summaries = []
    for p in planets:
        biomes = (await db.execute(select(Biome.name).where(Biome.planet_id == p.id, Biome.lifecycle_state.in_(["SEED", "ACTIVE", "MATURE"])))).scalars().all()
        planet_summaries.append(PlanetSummary(id=p.id, name=p.name, stardust_count=p.stardust_count, health_status=p.health_status, active_biomes=list(biomes), color=p.color or "#6D28D9", planet_type=p.planet_type or "standard"))
    return GalaxyStatusResponse(galaxy_id=galaxy.id, galaxy_name=galaxy.name, strength_score=galaxy.strength_score, total_stardust=total_stardust, total_entities=total_entities, planets=planet_summaries, contradiction_count_unresolved=unresolved)


# ── Galaxy Join (H2.7) ──────────────────────────────────────────────────────

import secrets
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel as _BM


class InviteRequest(_BM):
    planet_id: str | None = None
    role: str = "member"


class JoinRequest(_BM):
    invite_token: str
    email: str
    name: str
    password: str


@router.post("/invite")
async def create_invite(body: InviteRequest, user: User = Depends(get_current_user), galaxy: Galaxy = Depends(get_galaxy_for_user), db: AsyncSession = Depends(get_db)):
    if user.role not in ("owner", "admin"):
        raise HTTPException(403, "Only owner/admin can create invites")
    invite = GalaxyInvite(
        id=str(uuid4()), galaxy_id=galaxy.id, planet_id=body.planet_id,
        invited_by=user.id, role=body.role, token=secrets.token_urlsafe(32),
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7),
    )
    db.add(invite)
    await db.commit()
    return {"invite_id": invite.id, "token": invite.token, "expires_at": invite.expires_at.isoformat()}


@router.post("/join")
async def join_galaxy(body: JoinRequest, db: AsyncSession = Depends(get_db)):
    invite = (await db.execute(
        select(GalaxyInvite).where(GalaxyInvite.token == body.invite_token, GalaxyInvite.used_at.is_(None))
    )).scalar_one_or_none()
    if not invite:
        raise HTTPException(400, "Invalid or already-used invite")
    if invite.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(400, "Invite expired")
    existing = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "Email already registered")
    new_user = User(
        id=str(uuid4()), email=body.email, name=body.name,
        password_hash=hash_password(body.password), role=invite.role,
        galaxy_id=invite.galaxy_id, planet_id=invite.planet_id,
    )
    db.add(new_user)
    invite.used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    invite.used_by = new_user.id
    await db.flush()
    token = await create_session(new_user, db)
    return {"token": token, "user_id": new_user.id, "galaxy_id": invite.galaxy_id, "planet_id": invite.planet_id, "role": invite.role}
