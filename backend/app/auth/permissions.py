"""RBAC permission checker — enforces Planet-level access control."""
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, PlanetAccessGrant, PermissionCheck


class PermissionChecker:

    async def can_access_planet(
        self, user: User, planet_id: str, action: str, db: AsyncSession,
    ) -> bool:
        """Check if user can perform action on planet. Logs every check."""
        # Owner and admin always have access
        if user.role in ("owner", "admin"):
            await self._log(user.id, "planet", planet_id, action, True, None, db)
            return True

        # Member/viewer: check assigned planet
        if user.planet_id == planet_id:
            if action == "read" or user.role == "member":
                await self._log(user.id, "planet", planet_id, action, True, None, db)
                return True
            if user.role == "viewer" and action == "write":
                await self._log(user.id, "planet", planet_id, action, False, "viewer_write", db)
                return False

        # Check explicit grants
        grant = (await db.execute(
            select(PlanetAccessGrant).where(
                PlanetAccessGrant.user_id == user.id,
                PlanetAccessGrant.planet_id == planet_id,
                or_(PlanetAccessGrant.expires_at.is_(None), PlanetAccessGrant.expires_at > datetime.now(timezone.utc).replace(tzinfo=None)),
            )
        )).scalar_one_or_none()

        if grant:
            permitted = action == "read" or grant.access_type == "READ_WRITE"
            await self._log(user.id, "planet", planet_id, action, permitted,
                            None if permitted else "read_only_grant", db)
            return permitted

        await self._log(user.id, "planet", planet_id, action, False, "no_access", db)
        return False

    async def require_planet_access(
        self, user: User, planet_id: str, action: str, db: AsyncSession,
    ) -> None:
        """Raise 403 if user cannot access the Planet."""
        if not await self.can_access_planet(user, planet_id, action, db):
            raise HTTPException(403, "Access denied.")

    async def _log(
        self, user_id: str, resource_type: str, resource_id: str,
        action: str, permitted: bool, denial_reason: str | None, db: AsyncSession,
    ) -> None:
        db.add(PermissionCheck(
            user_id=user_id, resource_type=resource_type,
            resource_id=resource_id, action=action,
            permitted=permitted, denial_reason=denial_reason,
        ))
        # Don't commit — let the caller's transaction handle it


permission_checker = PermissionChecker()
