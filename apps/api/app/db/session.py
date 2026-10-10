from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def _sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


@asynccontextmanager
async def org_session(org_id: UUID) -> AsyncIterator[AsyncSession]:
    """Tenant-scoped transaction. `app.org_id` is transaction-local (is_local=true),
    so it can never leak to another request through the connection pool."""
    async with _sessionmaker()() as s, s.begin():
        await s.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": str(org_id)})
        yield s


@asynccontextmanager
async def admin_session() -> AsyncIterator[AsyncSession]:
    """BYPASSRLS session. Only /admin routers and platform jobs may use this."""
    engine = create_async_engine(get_settings().database_admin_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as s, s.begin():
            yield s
    finally:
        await engine.dispose()
