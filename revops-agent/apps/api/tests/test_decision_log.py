import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.session import org_session
from app.models.audit import DecisionLog
from app.services.decision_log import GENESIS, log, verify_chain
from app.utils.canonical import canonical_json
from tests.helpers import SeededOrg, assert_logged


async def _log(org, n=1, **kw):  # type: ignore[no-untyped-def]
    for i in range(n):
        async with org_session(org) as s:
            await log(
                s, org_id=org, actor_type=kw.get("actor_type", "system"), actor_id="t",
                event=kw.get("event", "finding.created"), entity_type="finding",
                entity_id=uuid4(), data={"i": i, "nested": {"b": 1, "a": [1, 2]}},
            )  # fmt: skip


def test_canonical_json_is_stable() -> None:
    a = {"b": 1, "a": [datetime(2026, 1, 1, tzinfo=UTC), Decimal("1.5")], "ü": "é"}
    b = {"ü": "é", "a": [datetime(2026, 1, 1, tzinfo=UTC), Decimal("1.5")], "b": 1}
    assert canonical_json(a) == canonical_json(b)
    assert canonical_json({"x": 1}) == '{"x":1}'
    assert "é" in canonical_json({"k": "é"})  # not ASCII-escaped


async def test_chain_links_from_genesis_and_verifies(seeded: SeededOrg) -> None:
    await _log(seeded.org_id, 5)
    async with org_session(seeded.org_id) as s:
        rows = (await s.execute(select(DecisionLog).order_by(DecisionLog.id))).scalars().all()
        assert rows[0].prev_hash == GENESIS
        assert all(rows[i].prev_hash == rows[i - 1].hash for i in range(1, 5))
        res = await verify_chain(s, seeded.org_id)
    assert res.ok and res.checked == 5 and res.first_bad_id is None


async def test_verify_range(seeded: SeededOrg) -> None:
    await _log(seeded.org_id, 6)
    async with org_session(seeded.org_id) as s:
        ids = [
            r for r in (await s.execute(select(DecisionLog.id).order_by(DecisionLog.id))).scalars()
        ]
        res = await verify_chain(s, seeded.org_id, ids[2], ids[4])
    assert res.ok and res.checked == 3


async def test_chains_are_per_org(seeded: SeededOrg, owner_engine: AsyncEngine) -> None:
    from tests.helpers import drop_org, seed_org

    other = await seed_org(owner_engine)
    try:
        await _log(seeded.org_id, 2)
        await _log(other.org_id, 2)
        async with org_session(other.org_id) as s:
            first = (
                (await s.execute(select(DecisionLog).order_by(DecisionLog.id))).scalars().first()
            )
            assert first is not None and first.prev_hash == GENESIS  # not chained to the other org
            assert (await verify_chain(s, other.org_id)).ok
    finally:
        await drop_org(owner_engine, other)


async def _tamper(engine: AsyncEngine, sql: str, **params: object) -> None:
    async with engine.begin() as c:
        await c.execute(
            text("SET LOCAL session_replication_role = replica")
        )  # bypass append-only trigger
        await c.execute(text(sql), params)


async def test_tampered_data_is_detected_at_that_row(
    seeded: SeededOrg, owner_engine: AsyncEngine
) -> None:
    await _log(seeded.org_id, 5)
    async with org_session(seeded.org_id) as s:
        ids = list((await s.execute(select(DecisionLog.id).order_by(DecisionLog.id))).scalars())
    await _tamper(
        owner_engine, "UPDATE decision_log SET data = '{\"i\": 99}'::jsonb WHERE id = :i", i=ids[2]
    )
    async with org_session(seeded.org_id) as s:
        res = await verify_chain(s, seeded.org_id)
        assert not res.ok and res.first_bad_id == ids[2]
        assert (
            await verify_chain(s, seeded.org_id, ids[3], ids[4])
        ).ok  # untouched range still valid


async def test_tampered_event_and_actor_are_detected(
    seeded: SeededOrg, owner_engine: AsyncEngine
) -> None:
    await _log(seeded.org_id, 3)
    async with org_session(seeded.org_id) as s:
        ids = list((await s.execute(select(DecisionLog.id).order_by(DecisionLog.id))).scalars())
    await _tamper(
        owner_engine, "UPDATE decision_log SET event = 'card.approved' WHERE id = :i", i=ids[1]
    )
    async with org_session(seeded.org_id) as s:
        assert (await verify_chain(s, seeded.org_id)).first_bad_id == ids[1]


async def test_deleted_row_is_detected_at_next_row(
    seeded: SeededOrg, owner_engine: AsyncEngine
) -> None:
    await _log(seeded.org_id, 5)
    async with org_session(seeded.org_id) as s:
        ids = list((await s.execute(select(DecisionLog.id).order_by(DecisionLog.id))).scalars())
    await _tamper(owner_engine, "DELETE FROM decision_log WHERE id = :i", i=ids[2])
    async with org_session(seeded.org_id) as s:
        res = await verify_chain(s, seeded.org_id)
    assert not res.ok and res.first_bad_id == ids[3]


async def test_forged_hash_with_valid_math_but_wrong_link_is_detected(
    seeded: SeededOrg, owner_engine: AsyncEngine
) -> None:
    await _log(seeded.org_id, 3)
    async with org_session(seeded.org_id) as s:
        ids = list((await s.execute(select(DecisionLog.id).order_by(DecisionLog.id))).scalars())
    await _tamper(
        owner_engine, "UPDATE decision_log SET prev_hash = 'GENESIS' WHERE id = :i", i=ids[1]
    )
    async with org_session(seeded.org_id) as s:
        assert (await verify_chain(s, seeded.org_id)).first_bad_id == ids[1]


async def test_100_concurrent_inserts_keep_chain_valid(seeded: SeededOrg) -> None:
    async def one(i: int) -> None:
        async with org_session(seeded.org_id) as s:
            await log(
                s, org_id=seeded.org_id, actor_type="agent", actor_id=f"w{i}", event="finding.updated",
                entity_type="finding", entity_id=uuid4(), data={"i": i},
            )  # fmt: skip

    await asyncio.gather(*(one(i) for i in range(100)))
    async with org_session(seeded.org_id) as s:
        rows = (await s.execute(select(DecisionLog).order_by(DecisionLog.id))).scalars().all()
        assert len(rows) == 100
        assert len({r.hash for r in rows}) == 100 and len({r.prev_hash for r in rows}) == 100
        assert rows[0].prev_hash == GENESIS
        assert all(rows[i].prev_hash == rows[i - 1].hash for i in range(1, 100))
        assert (await verify_chain(s, seeded.org_id)).ok


async def test_rollback_leaves_no_entry_and_state_change_is_atomic(seeded: SeededOrg) -> None:
    with pytest.raises(RuntimeError):
        async with org_session(seeded.org_id) as s:
            await log(s, org_id=seeded.org_id, actor_type="user", actor_id="u", event="card.approved",
                      entity_type="action_card", entity_id=uuid4())  # fmt: skip
            raise RuntimeError("state change failed")
    async with org_session(seeded.org_id) as s:
        assert (await s.execute(select(DecisionLog))).first() is None


async def test_assert_logged_helper(seeded: SeededOrg) -> None:
    eid = uuid4()
    async with org_session(seeded.org_id) as s:
        await log(s, org_id=seeded.org_id, actor_type="user", actor_id="u", event="card.approved",
                  entity_type="action_card", entity_id=eid)  # fmt: skip
    await assert_logged(seeded.org_id, "card.approved", entity_id=eid)
    with pytest.raises(AssertionError):
        await assert_logged(seeded.org_id, "card.rejected", entity_id=eid)
    with pytest.raises(AssertionError):  # exactly once
        async with org_session(seeded.org_id) as s:
            await log(s, org_id=seeded.org_id, actor_type="user", actor_id="u", event="card.approved",
                      entity_type="action_card", entity_id=eid)  # fmt: skip
        await assert_logged(seeded.org_id, "card.approved", entity_id=eid)
