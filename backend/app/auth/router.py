"""Authentication REST endpoints."""
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Galaxy
from app.models.user import User
from app.auth.service import hash_password, verify_password, create_session, invalidate_token
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    token: str
    user_id: str
    email: str
    name: str
    role: str


class UserProfile(BaseModel):
    id: str
    email: str
    name: str
    role: str
    galaxy_id: str | None
    planet_id: str | None


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    # Check if email already taken
    existing = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "Email already registered")

    # MVP: one user per Galaxy. Check if any Galaxy exists with an owner.
    existing_owner = (await db.execute(select(User).where(User.role == "owner"))).scalar_one_or_none()
    if existing_owner:
        raise HTTPException(400, "A Galaxy owner already exists. Use /auth/login or wait for Galaxy Join (H2.7).")

    user = User(
        id=str(uuid4()),
        email=body.email,
        name=body.name,
        password_hash=hash_password(body.password),
        role="owner",
    )
    # Bind to existing Galaxy if one exists (from onboarding)
    galaxy = (await db.execute(select(Galaxy).limit(1))).scalar_one_or_none()
    if galaxy:
        user.galaxy_id = galaxy.id

    db.add(user)
    await db.flush()

    token = await create_session(user, db, user_agent=request.headers.get("user-agent"), ip_address=request.client.host if request.client else None)
    return TokenResponse(token=token, user_id=user.id, email=user.email, name=user.name, role=user.role)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "Account is deactivated")

    token = await create_session(user, db, user_agent=request.headers.get("user-agent"), ip_address=request.client.host if request.client else None)
    return TokenResponse(token=token, user_id=user.id, email=user.email, name=user.name, role=user.role)


@router.post("/logout", status_code=204)
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        await invalidate_token(auth[7:], db)


@router.get("/me", response_model=UserProfile)
async def me(user: User = Depends(get_current_user)):
    return UserProfile(
        id=user.id, email=user.email, name=user.name,
        role=user.role, galaxy_id=user.galaxy_id, planet_id=user.planet_id,
    )
