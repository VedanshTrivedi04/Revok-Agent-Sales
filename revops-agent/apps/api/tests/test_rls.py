"""RLS isolation across EVERY table with an org_id column (auto-discovered from metadata).

Rows are inserted as the `owner` superuser (bypasses RLS; FK checks disabled so generic rows
can be generated), then read/modified as the `app` role through org_session().
"""

import re
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    Float,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    Table,
    Text,
    delete,
    func,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app import models  # noqa: F401
from app.config import get_settings
from app.db.base import Base
from app.db.session import org_session

TENANT_TABLES: list[Table] = [
    t for t in Base.metadata.sorted_tables if "org_id" in t.c or t.name == "organizations"
]


def _check_values(table: Table, column: Column[Any]) -> Any | None:
    for c in table.constraints:
        if isinstance(c, CheckConstraint) and re.match(rf"^{column.name} IN \(", str(c.sqltext)):
            first = re.search(r"\((.*?)(,|\))", str(c.sqltext))
            assert first
            raw = first.group(1).strip()
            return int(raw) if raw.isdigit() else raw.strip("'")
    return None


def _value(table: Table, column: Column[Any], org_id: UUID, uniq: str) -> Any:
    if column.name == "org_id" or (table.name == "organizations" and column.name == "id"):
        return org_id
    allowed = _check_values(table, column)
    if allowed is not None:
        return allowed
    t = column.type
    if isinstance(t, PG_UUID):
        return uuid4()
    if isinstance(t, ARRAY):
        return []
    if isinstance(t, (Integer, SmallInteger, BigInteger)):
        return 1
    if isinstance(t, (Numeric, Float)):
        return 1
    if isinstance(t, Boolean):
        return True
    if isinstance(t, Date):
        return date.today()
    if isinstance(t, LargeBinary):
        return b"x"
    if type(t).__name__ == "TIMESTAMP" or "DateTime" in type(t).__name__:
        return datetime.now(UTC)
    if type(t).__name__ == "JSONB":
        return {}
    if isinstance(t, Text) or type(t).__name__ in ("CITEXT", "String"):
        return f"{column.name}-{uniq}"
    raise AssertionError(f"no generator for {table.name}.{column.name}: {t!r}")


def _row(table: Table, org_id: UUID) -> dict[str, Any]:
    uniq = uuid4().hex
    return {
        col.name: _value(table, col, org_id, uniq)
        for col in table.columns
        if col.identity is None
        and (col.name == "org_id" or (not col.nullable and col.server_default is None))
    }


def _owner_url() -> str:
    return get_settings().database_migrator_url.replace("+psycopg", "+asyncpg")


@pytest_asyncio.fixture
async def owner_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(_owner_url())
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def two_orgs(owner_engine: AsyncEngine) -> AsyncIterator[tuple[UUID, UUID]]:
    org_a, org_b = uuid4(), uuid4()
    async with owner_engine.begin() as conn:
        await conn.execute(text("SET LOCAL session_replication_role = replica"))
        orgs = Base.metadata.tables["organizations"]
        for org in (org_a, org_b):
            await conn.execute(orgs.insert().values(_row(orgs, org)))
        for table in TENANT_TABLES:
            if table.name == "organizations":
                continue
            for org in (org_a, org_b):
                await conn.execute(table.insert().values(_row(table, org)))
    yield org_a, org_b
    async with owner_engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM organizations WHERE id = ANY(:ids)"), {"ids": [org_a, org_b]}
        )


def test_discovery_finds_all_tenant_tables() -> None:
    names = {t.name for t in TENANT_TABLES}
    assert len(names) >= 27
    assert {"organizations", "action_cards", "decision_log", "memberships", "events"} <= names
    # global tables must stay out of RLS
    assert not names & {"users", "failed_jobs", "feature_flags"}


@pytest.mark.parametrize("table", TENANT_TABLES, ids=lambda t: t.name)
async def test_rls_enabled_and_forced(table: Table, owner_engine: AsyncEngine) -> None:
    async with owner_engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = :n"),
                {"n": table.name},
            )
        ).one()
        pol = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM pg_policies WHERE tablename = :n AND policyname = 'tenant_isolation'"
                ),
                {"n": table.name},
            )
        ).scalar()
    assert tuple(row) == (True, True)
    assert pol == 1


@pytest.mark.parametrize("table", TENANT_TABLES, ids=lambda t: t.name)
async def test_org_a_cannot_touch_org_b(table: Table, two_orgs: tuple[UUID, UUID]) -> None:
    org_a, org_b = two_orgs
    key = table.c.id if table.name == "organizations" else table.c.org_id

    async with org_session(org_a) as s:
        # read: only own rows
        seen = set((await s.execute(select(key))).scalars().all())
        assert seen == {org_a}
        assert (
            await s.execute(select(func.count()).select_from(table).where(key == org_b))
        ).scalar() == 0

        # update: other tenant's rows are invisible, so nothing is affected
        if table.name != "decision_log":
            res = await s.execute(update(table).where(key == org_b).values({key.name: org_b}))
            assert res.rowcount == 0

    async with org_session(org_a) as s:
        # delete: nothing affected (decision_log has no DELETE grant at all, covered below)
        if table.name != "decision_log":
            res = await s.execute(delete(table).where(key == org_b))
            assert res.rowcount == 0

    # B's rows are still there
    async with org_session(org_b) as s:
        assert (await s.execute(select(func.count()).select_from(table))).scalar() == 1


@pytest.mark.parametrize(
    "table", [t for t in TENANT_TABLES if t.name != "organizations"], ids=lambda t: t.name
)
async def test_cannot_insert_into_other_tenant(table: Table, two_orgs: tuple[UUID, UUID]) -> None:
    org_a, org_b = two_orgs
    with pytest.raises(DBAPIError, match="row-level security"):
        async with org_session(org_a) as s:
            await s.execute(table.insert().values(_row(table, org_b)))


async def test_no_org_context_sees_nothing(two_orgs: tuple[UUID, UUID]) -> None:
    from app.db.session import get_engine

    async with get_engine().begin() as conn:
        for table in TENANT_TABLES:
            n = (await conn.execute(select(func.count()).select_from(table))).scalar()
            assert n == 0, table.name


async def test_decision_log_is_append_only_for_app_role(two_orgs: tuple[UUID, UUID]) -> None:
    org_a, _ = two_orgs
    for stmt in ("UPDATE decision_log SET event = 'x'", "DELETE FROM decision_log"):
        with pytest.raises(DBAPIError, match="permission denied"):
            async with org_session(org_a) as s:
                await s.execute(text(stmt))


async def test_decision_log_update_blocked_even_for_owner(
    two_orgs: tuple[UUID, UUID], owner_engine: AsyncEngine
) -> None:
    with pytest.raises(DBAPIError, match="append-only"):
        async with owner_engine.begin() as conn:
            await conn.execute(text("UPDATE decision_log SET event = 'x'"))
