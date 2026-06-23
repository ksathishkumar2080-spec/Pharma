from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from shared.config import get_settings
import logging

log = logging.getLogger(__name__)

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.postgres_dsn,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # detect stale connections
            pool_recycle=3600,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


# Alias used by compliance middleware and other services
async_session_factory = get_session_factory


async def get_session() -> AsyncSession:
    """FastAPI dependency that yields a session and handles commit/rollback."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Legacy alias kept for backward compatibility
async def get_db() -> AsyncSession:
    async with get_session_factory()() as session:
        yield session
