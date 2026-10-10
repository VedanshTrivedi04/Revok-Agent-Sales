from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import get_settings
from app.db import session as db_session
from app.main import create_app
from app.utils.redis import close_redis
from tests.helpers import SeededOrg, drop_org, seed_org


@pytest_asyncio.fixture(autouse=True)
async def _fresh_engine() -> AsyncIterator[None]:
    """Each test gets its own engine and Redis client (bound to the test's event loop)."""
    db_session.get_engine.cache_clear()
    db_session._sessionmaker.cache_clear()
    yield
    await db_session.get_engine().dispose()
    db_session.get_engine.cache_clear()
    db_session._sessionmaker.cache_clear()
    await close_redis()


@pytest_asyncio.fixture
async def owner_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(
        get_settings().database_migrator_url.replace("+psycopg", "+asyncpg")
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(owner_engine: AsyncEngine) -> AsyncIterator[SeededOrg]:
    s = await seed_org(owner_engine)
    yield s
    await drop_org(owner_engine, s)


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        yield c
