"""Shared test harness.

Infrastructure (TEST_INFRA env var):
  containers (default)  throw-away Postgres 16 + Redis 7 via testcontainers, migrated to head
  compose               use the dev stack from `make up` (localhost:5433 / 6379)

Fixtures: owner_engine (superuser, bypasses RLS), org_a / org_b (one org each, a user per role),
users_by_role, client_as(role, org=...), plus `respx_mock` (HTTP mocking) from the respx plugin.
"""

import os
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from uuid import UUID

import psycopg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import get_settings
from app.db import session as db_session
from app.main import create_app
from app.utils.redis import close_redis
from tests.helpers import SeededOrg, bearer, drop_org, mint_jwt, seed_org

API_ROOT = Path(__file__).resolve().parents[1]
INIT_SQL = API_ROOT.parents[1] / "infra" / "db" / "init.sql"


def _migrate() -> None:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session", autouse=True)
def infra() -> Iterator[None]:
    """Point the app at disposable Postgres/Redis (default) or the compose stack."""
    if os.environ.get("TEST_INFRA", "containers") == "compose":
        get_settings.cache_clear()
        yield
        return

    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer

    with (
        PostgresContainer("postgres:16", username="owner", password="owner", dbname="revops") as pg,
        RedisContainer("redis:7") as rd,
    ):
        host, port = pg.get_container_host_ip(), pg.get_exposed_port(5432)
        with psycopg.connect(
            f"postgresql://owner:owner@{host}:{port}/revops", autocommit=True
        ) as conn:
            conn.execute(INIT_SQL.read_text(encoding="utf-8"))  # roles: app / admin
        os.environ.update(
            DATABASE_URL=f"postgresql+asyncpg://app:app@{host}:{port}/revops",
            DATABASE_ADMIN_URL=f"postgresql+asyncpg://admin:admin@{host}:{port}/revops",
            DATABASE_MIGRATOR_URL=f"postgresql+psycopg://owner:owner@{host}:{port}/revops",
            REDIS_URL=f"redis://{rd.get_container_host_ip()}:{rd.get_exposed_port(6379)}/0",
        )
        get_settings.cache_clear()
        _migrate()
        yield
    get_settings.cache_clear()


@pytest_asyncio.fixture(autouse=True)
async def _fresh_engine() -> AsyncIterator[None]:
    """Each test gets its own engine and Redis client (bound to the test's event loop)."""
    db_session.get_engine.cache_clear()
    db_session._sessionmaker.cache_clear()
    db_session.get_admin_engine.cache_clear()
    db_session._admin_sessionmaker.cache_clear()
    yield
    await db_session.get_engine().dispose()
    await db_session.get_admin_engine().dispose()
    db_session.get_engine.cache_clear()
    db_session._sessionmaker.cache_clear()
    db_session.get_admin_engine.cache_clear()
    db_session._admin_sessionmaker.cache_clear()
    await close_redis()


@pytest_asyncio.fixture
async def owner_engine() -> AsyncIterator[AsyncEngine]:
    url = get_settings().database_migrator_url.replace("+psycopg", "+asyncpg")
    engine = create_async_engine(url)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(owner_engine: AsyncEngine) -> AsyncIterator[SeededOrg]:
    s = await seed_org(owner_engine)
    yield s
    await drop_org(owner_engine, s)


@pytest_asyncio.fixture
async def org_a(seeded: SeededOrg) -> SeededOrg:
    """Primary tenant (alias of `seeded`): an org with one user per role."""
    return seeded


@pytest_asyncio.fixture
async def org_b(owner_engine: AsyncEngine) -> AsyncIterator[SeededOrg]:
    """A second tenant for isolation tests."""
    s = await seed_org(owner_engine)
    yield s
    await drop_org(owner_engine, s)


@pytest.fixture
def users_by_role(org_a: SeededOrg) -> dict[str, UUID]:
    return org_a.users


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        yield c


@pytest_asyncio.fixture
async def client_as(org_a: SeededOrg) -> AsyncIterator[Callable[..., AsyncClient]]:
    """`client_as("manager")` -> API client authenticated as that role (default org_a).

    The role in the token is irrelevant to the API (it reads the DB); the user id is what counts.
    """
    made: list[AsyncClient] = []
    app = create_app()

    def factory(role: str, org: SeededOrg | None = None) -> AsyncClient:
        o = org or org_a
        c = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://t",
            headers=bearer(mint_jwt(o.users[role], o.org_id)),
        )
        made.append(c)
        return c

    yield factory
    for c in made:
        await c.aclose()
