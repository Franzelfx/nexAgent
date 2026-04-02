"""Shared test fixtures for NexAgent."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nexagent.config import settings
from nexagent.models.base import SCHEMA, Base


async def _bootstrap_engine():
    """Create a fresh engine and ensure schema + tables exist."""
    eng = create_async_engine(settings.database_url, echo=False)
    async with eng.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        await conn.run_sync(Base.metadata.create_all)
    return eng


@pytest.fixture
async def db_session():
    """Yield an async session that rolls back after each test.

    A fresh engine is created per test so that all connections live on
    the current event loop (pytest-asyncio uses one loop per test by default).
    Service functions only ``flush()`` (never ``commit()``), so a final
    ``rollback()`` undoes all writes made during the test.
    """
    engine = await _bootstrap_engine()
    session = AsyncSession(engine, expire_on_commit=False)
    yield session
    await session.rollback()
    await session.close()
    await engine.dispose()
