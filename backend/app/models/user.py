from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text, Integer, DateTime, Boolean, ForeignKey, UniqueConstraint, true, func
from datetime import datetime
from app.models.galaxy import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_login: Mapped[datetime | None] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    role: Mapped[str] = mapped_column(Text, server_default="owner")
    galaxy_id: Mapped[str | None] = mapped_column(Text, ForeignKey("galaxies.id"))
    planet_id: Mapped[str | None] = mapped_column(Text, ForeignKey("planets.id"))
    preferences: Mapped[str] = mapped_column(Text, server_default="{}")
    api_key: Mapped[str | None] = mapped_column(Text, unique=True)
    api_key_created_at: Mapped[datetime | None] = mapped_column(DateTime)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_used: Mapped[datetime | None] = mapped_column(DateTime)
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(Text)


class PlanetAccessGrant(Base):
    __tablename__ = "planet_access_grants"
    __table_args__ = (UniqueConstraint("user_id", "planet_id", name="uq_user_planet_grant"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    planet_id: Mapped[str] = mapped_column(Text, ForeignKey("planets.id"), nullable=False)
    access_type: Mapped[str] = mapped_column(Text, nullable=False)  # READ_ONLY | READ_WRITE
    granted_by: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)


class PermissionCheck(Base):
    __tablename__ = "permission_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    permitted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    denial_reason: Mapped[str | None] = mapped_column(Text)


class GalaxyInvite(Base):
    __tablename__ = "galaxy_invites"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    galaxy_id: Mapped[str] = mapped_column(Text, ForeignKey("galaxies.id"), nullable=False)
    planet_id: Mapped[str | None] = mapped_column(Text, ForeignKey("planets.id"))
    invited_by: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(Text, server_default="member")
    token: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    used_by: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"))
