from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
from app.config import get_settings

settings = get_settings()


def create_engine_from_url(database_url: str) -> AsyncEngine:
    """Create async engine. Supports PostgreSQL (production) and SQLite (tests)."""
    if database_url.startswith("sqlite"):
        return create_async_engine(
            database_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
    return create_async_engine(
        database_url,
        echo=False,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_pre_ping=True,
    )


engine = create_engine_from_url(settings.DATABASE_URL)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
