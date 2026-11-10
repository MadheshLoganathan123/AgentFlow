import os
from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from packages.db.base import Base

# Database URLs from environment or sensible development defaults
DATABASE_URL_DEFAULT = "postgresql+asyncpg://agentflow:agentflow_dev_password@localhost:5432/agentflow"
DATABASE_URL_SYNC_DEFAULT = "postgresql+psycopg2://agentflow:agentflow_dev_password@localhost:5432/agentflow"

ASYNC_DATABASE_URL = os.getenv("DATABASE_URL", DATABASE_URL_DEFAULT)
SYNC_DATABASE_URL = os.getenv("DATABASE_URL_SYNC", DATABASE_URL_SYNC_DEFAULT)

# Adjust configuration for SQLite if used in test/dev
async_kwargs: dict = {"echo": False, "future": True}
sync_kwargs: dict = {"echo": False}

if "sqlite" in ASYNC_DATABASE_URL:
    async_kwargs["connect_args"] = {"check_same_thread": False}
    if ":memory:" in ASYNC_DATABASE_URL:
        async_kwargs["poolclass"] = StaticPool
else:
    async_kwargs["pool_pre_ping"] = True

if "sqlite" in SYNC_DATABASE_URL:
    sync_kwargs["connect_args"] = {"check_same_thread": False}
    if ":memory:" in SYNC_DATABASE_URL:
        sync_kwargs["poolclass"] = StaticPool
else:
    sync_kwargs["pool_pre_ping"] = True


def _create_async_engine_safe():
    """Create async engine, gracefully handling missing native drivers in test envs."""
    try:
        return create_async_engine(ASYNC_DATABASE_URL, **async_kwargs)
    except Exception as exc:  # pragma: no cover
        if "sqlite" in ASYNC_DATABASE_URL:
            raise
        # Fallback to sqlite for test environments where pg drivers are absent
        fallback_url = "sqlite+aiosqlite:///:memory:"
        fallback_kwargs = {
            "echo": False,
            "future": True,
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
        import warnings
        warnings.warn(
            f"Could not connect to {ASYNC_DATABASE_URL!r} ({exc}). "
            "Falling back to in-memory SQLite for safety.",
            stacklevel=2,
        )
        return create_async_engine(fallback_url, **fallback_kwargs)


def _create_sync_engine_safe():
    """Create sync engine, gracefully handling missing native drivers in test envs."""
    try:
        return create_engine(SYNC_DATABASE_URL, **sync_kwargs)
    except Exception as exc:  # pragma: no cover
        if "sqlite" in SYNC_DATABASE_URL:
            raise
        fallback_url = "sqlite:///:memory:"
        fallback_kwargs = {
            "echo": False,
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
        import warnings
        warnings.warn(
            f"Could not connect to {SYNC_DATABASE_URL!r} ({exc}). "
            "Falling back to in-memory SQLite for safety.",
            stacklevel=2,
        )
        return create_engine(fallback_url, **fallback_kwargs)


# Create engines
async_engine = _create_async_engine_safe()
sync_engine = _create_sync_engine_safe()

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_sync_session():
    """Context manager or utility for synchronous database session."""
    session = SyncSessionLocal()
    try:
        yield session
    finally:
        session.close()


async def init_db():
    """Create all tables in the configured database (useful for test environments)."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

