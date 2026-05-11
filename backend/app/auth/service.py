"""Authentication utilities: password hashing and JWT tokens."""
import hashlib
import hmac
import secrets
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User, UserSession

# JWT-like token: base64(user_id:expiry:signature) — no external dependency needed.
# For production SSO (H3.2), swap to python-jose or PyJWT.

TOKEN_EXPIRY_HOURS = 168  # 7 days



def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}:{h.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, h = password_hash.split(":")
        return hmac.compare_digest(
            h, hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
        )
    except (ValueError, AttributeError):
        return False


def generate_token(user_id: str) -> tuple[str, str, datetime]:
    """Return (raw_token, token_hash, expires_at)."""
    raw = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=TOKEN_EXPIRY_HOURS)
    return raw, token_hash, expires_at


async def create_session(
    user: User, db: AsyncSession, user_agent: str | None = None, ip_address: str | None = None
) -> str:
    """Create a user session, return the raw token."""
    raw, token_hash, expires_at = generate_token(user.id)
    session = UserSession(
        id=str(uuid4()),
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(session)
    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    return raw


async def validate_token(raw_token: str, db: AsyncSession) -> User | None:
    """Validate a raw token, return the User or None."""
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    sess = (
        await db.execute(
            select(UserSession).where(
                UserSession.token_hash == token_hash,
                UserSession.expires_at > datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
    ).scalar_one_or_none()
    if not sess:
        return None
    # Touch last_used
    sess.last_used = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()
    user = (await db.execute(select(User).where(User.id == sess.user_id, User.is_active == True))).scalar_one_or_none()
    return user


async def invalidate_token(raw_token: str, db: AsyncSession) -> bool:
    """Delete a session by raw token. Returns True if found."""
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    sess = (await db.execute(select(UserSession).where(UserSession.token_hash == token_hash))).scalar_one_or_none()
    if sess:
        await db.delete(sess)
        await db.commit()
        return True
    return False


async def prune_expired_sessions(db: AsyncSession) -> int:
    """Delete expired UserSession rows. Returns the number of rows deleted."""
    from sqlalchemy import delete as sql_delete
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    result = await db.execute(sql_delete(UserSession).where(UserSession.expires_at <= now))
    await db.commit()
    return result.rowcount
