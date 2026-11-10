import os
from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from packages.db.base import Base

# Database URLs from environment or sensible development defaults
DATABASE_URL_DEFAULT = "postgresql+asyncpg://agentflow:agentflow_dev_password@localhost:5432/agentflow"
DATABASE_URL_SYNC_DEFAULT = "postgresql+psycopg2://agentflow:agentflow_dev_password@localhost:5432/agentflow"

ASYNC_DATABASE_URL = os.getenv("DATABASE_URL", DATABASE_URL_DEFAULT)
SYNC_DATABASE_URL = os.getenv("DATABASE_URL_SYNC", DATABASE_URL_SYNC_DEFAULT)

# Adjust connect_args for SQLite if used in test/dev
async_connect_args = {}
sync_connect_args = {}
if "sqlite" in ASYNC_DATABASE_URL:
    async_connect_args = {"check_same_thread": False}
if "sqlite" in SYNC_DATABASE_URL:
    sync_connect_args = {"check_same_thread": False}

# Create engines with connection pooling
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
    connect_args=async_connect_args if "sqlite" in ASYNC_DATABASE_URL else {}
)

sync_engine = create_engine(
    SYNC_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args=sync_connect_args if "sqlite" in SYNC_DATABASE_URL else {}
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False
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
