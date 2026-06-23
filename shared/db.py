from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from shared.config import get_settings

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.postgres_dsn, pool_size=10, max_overflow=20)
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _session_factory


async def get_db() -> AsyncSession:
    async with get_session_factory()() as session:
        yield session
