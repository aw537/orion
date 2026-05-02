"""FastAPI dependencies for authentication."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import Galaxy
from app.models.user import User
from app.auth.service import validate_token


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    """Extract and validate user from Authorization header.

    When ORION_AUTH_DISABLED=true (local dev), returns a synthetic owner user
    bound to the first Galaxy. This preserves zero-friction local experience.
    """
    settings = get_settings()

    # Local dev bypass
    if getattr(settings, "ORION_AUTH_DISABLED", False):
        # Return the first persisted user if one exists
        user = (await db.execute(select(User).limit(1))).scalar_one_or_none()
        if user:
            return user
        # No user yet — create and persist a local dev user bound to first Galaxy
        galaxy = (await db.execute(select(Galaxy).limit(1))).scalar_one_or_none()
        dev_user = User(
            id="local-dev-user",
            email="dev@localhost",
            name="Local Developer",
            password_hash="",
            role="owner",
            galaxy_id=galaxy.id if galaxy else None,
        )
        db.add(dev_user)
        await db.flush()
        return dev_user

    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth[7:]  # strip "Bearer "
    user = await validate_token(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


async def get_galaxy_for_user(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Galaxy:
    """Get the Galaxy for the current user."""
    if not user.galaxy_id:
        raise HTTPException(status_code=404, detail="No galaxy found for user")
    galaxy = await db.get(Galaxy, user.galaxy_id)
    if not galaxy:
        raise HTTPException(status_code=404, detail="Galaxy not found")
    return galaxy
