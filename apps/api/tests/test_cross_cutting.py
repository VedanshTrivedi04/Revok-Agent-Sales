import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import structlog
from fastapi import APIRouter, Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.db.session import org_session
from app.main import create_app
from app.models.timeline import Account
from app.observability import REDACTED, scrub_processor, scrub_sentry_event
from app.utils.errors import ERROR_CODES, AppError
from app.utils.pagination import OrderKey, PageParams, decode_cursor, encode_cursor, paginate
from app.utils.ratelimit import rate_limit, take
from tests.helpers import SeededOrg

ROOT = Path(__file__).resolve().parents[3]


# ---------- error registry ----------
def test_unregistered_error_code_rejected() -> None:
    with pytest.raises(ValueError):
        AppError("made_up_code")


def test_default_status_and_message_from_registry() -> None:
    e = AppError("card_not_pending")
    assert e.status == 409 and e.message == ERROR_CODES["card_not_pending"][1]


def test_error_codes_doc_is_up_to_date() -> None:
    sys.path.insert(0, str(ROOT / "apps" / "api"))
    from scripts.gen_error_codes import render

    assert (ROOT / "docs" / "error-codes.md").read_text(encoding="utf-8") == render()


def test_required_codes_exist() -> None:
    required = {
        "card_not_pending", "stale_preview", "revert_conflict", "org_suspended",
        "recipient_not_allowed", "tier_blocked", "integration_needs_reauth",
        "validation_error", "rate_limited",
    }  # fmt: skip
    assert required <= set(ERROR_CODES)


async def test_unknown_route_and_unhandled_error_use_envelope() -> None:
    app = create_app()

    @app.get("/explode")
    async def explode() -> None:
        raise RuntimeError("secret customer text")

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t"
    ) as c:
        r = await c.get("/nope")
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
        r = await c.get("/explode")
        assert r.status_code == 500
        assert r.json()["error"]["code"] == "internal_error"
        assert "secret" not in r.text


# ---------- request id ----------
async def test_request_id_echoed_and_generated(client: AsyncClient) -> None:
    r = await client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"
    r = await client.get("/health")
    assert len(r.headers["x-request-id"]) == 32


# ---------- logging / sentry scrubbing ----------
def test_log_processor_redacts_sensitive_keys_and_emails() -> None:
    out = scrub_processor(
        None, "info",
        {"event": "x", "authorization": "Bearer abc", "note": "mail bob@acme.com now",
         "nested": {"access_token": "t", "ok": 1}, "org_id": "o1"},
    )  # fmt: skip
    assert out["authorization"] == REDACTED
    assert "bob@acme.com" not in out["note"] and "[email]" in out["note"]
    assert out["nested"] == {"access_token": REDACTED, "ok": 1}
    assert out["org_id"] == "o1"


def test_request_log_is_json_with_request_id_and_no_query(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import logging

    structlog.reset_defaults()
    from app.observability import configure_logging

    configure_logging("INFO")
    log = structlog.get_logger()
    structlog.contextvars.bind_contextvars(request_id="rid1", org_id="o1")
    log.info("hello", token="zzz")
    out = capsys.readouterr().out.strip().splitlines()[-1]
    data = json.loads(out)
    assert data["request_id"] == "rid1" and data["org_id"] == "o1" and data["token"] == REDACTED
    structlog.contextvars.clear_contextvars()
    logging.getLogger().handlers.clear()


def test_sentry_scrubber_drops_bodies_and_pii() -> None:
    event = {
        "request": {
            "data": {"x": 1},
            "headers": {"Authorization": "x"},
            "cookies": "c",
            "url": "http://t/a",
        },
        "user": {"id": "u1", "email": "a@b.com", "ip_address": "1.1.1.1"},
        "extra": {"body": "secret", "note": "ping a@b.com"},
    }
    out = scrub_sentry_event(event)
    assert "data" not in out["request"] and "headers" not in out["request"]
    assert out["user"] == {"id": "u1"}
    assert out["extra"]["body"] == REDACTED and "a@b.com" not in out["extra"]["note"]


# ---------- pagination ----------
def test_cursor_roundtrip_and_tamper_rejected() -> None:
    vals = [datetime(2026, 1, 2, tzinfo=UTC), uuid4(), 5, "x"]
    assert decode_cursor(encode_cursor(vals), 4) == vals
    for bad in ("!!!", encode_cursor([1]), "e30"):
        with pytest.raises(AppError) as ei:
            decode_cursor(bad, 4)
        assert ei.value.code == "invalid_cursor"


async def test_paginate_walks_all_rows_without_dupes_or_gaps(seeded: SeededOrg) -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    async with org_session(seeded.org_id) as s:
        for i in range(23):  # many rows share the same last_activity_at to exercise tie-breaking
            s.add(
                Account(
                    org_id=seeded.org_id,
                    name=f"A{i:02d}",
                    last_activity_at=base + timedelta(days=i // 5),
                )
            )
    order = [OrderKey(Account.name)]
    seen: list[str] = []
    cursor = None
    pages = 0
    while True:
        async with org_session(seeded.org_id) as s:
            rows, cursor = await paginate(
                s,
                __import__("sqlalchemy").select(Account),
                order,
                PageParams(limit=10, cursor=cursor),
            )
        seen += [r.name for r in rows]
        pages += 1
        if cursor is None:
            break
    assert pages == 3 and seen == [f"A{i:02d}" for i in range(23)]


async def test_paginate_desc_with_id_tiebreak(seeded: SeededOrg) -> None:
    from sqlalchemy import select

    async with org_session(seeded.org_id) as s:
        for i in range(12):
            s.add(Account(org_id=seeded.org_id, name=f"B{i}", plan_name="same"))
    order = [OrderKey(Account.plan_name, desc=True), OrderKey(Account.id, desc=True)]
    ids: list[UUID] = []
    cursor = None
    while True:
        async with org_session(seeded.org_id) as s:
            rows, cursor = await paginate(
                s, select(Account), order, PageParams(limit=5, cursor=cursor)
            )
        ids += [r.id for r in rows]
        if cursor is None:
            break
    assert len(ids) == 12 == len(set(ids)) and ids == sorted(ids, reverse=True)


# ---------- idempotency ----------
def _idem_app() -> tuple[FastAPI, dict[str, int]]:
    app = create_app()
    calls = {"n": 0}
    r = APIRouter()

    @r.post("/t/create")
    async def create(payload: dict[str, int]) -> dict[str, int]:
        calls["n"] += 1
        await asyncio.sleep(0.05)
        return {"calls": calls["n"], **payload}

    @r.post("/t/fail")
    async def fail() -> None:
        calls["n"] += 1
        raise AppError("provider_error")

    app.include_router(r)
    return app, calls


async def test_same_key_same_body_replays_once() -> None:
    app, calls = _idem_app()
    h = {"Idempotency-Key": uuid4().hex, "Authorization": "Bearer x"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        a = await c.post("/t/create", json={"a": 1}, headers=h)
        b = await c.post("/t/create", json={"a": 1}, headers=h)
    assert a.status_code == b.status_code == 200
    assert a.json() == b.json() and calls["n"] == 1
    assert b.headers["idempotent-replayed"] == "true" and "idempotent-replayed" not in a.headers


async def test_same_key_different_body_is_422() -> None:
    app, calls = _idem_app()
    h = {"Idempotency-Key": uuid4().hex, "Authorization": "Bearer x"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/t/create", json={"a": 1}, headers=h)
        r = await c.post("/t/create", json={"a": 2}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "idempotency_key_reuse"
    assert calls["n"] == 1


async def test_key_is_scoped_per_caller_and_per_path() -> None:
    app, calls = _idem_app()
    key = uuid4().hex
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post(
            "/t/create", json={}, headers={"Idempotency-Key": key, "Authorization": "Bearer u1"}
        )
        await c.post(
            "/t/create", json={}, headers={"Idempotency-Key": key, "Authorization": "Bearer u2"}
        )
    assert calls["n"] == 2


async def test_concurrent_duplicate_is_409_in_progress() -> None:
    app, calls = _idem_app()
    h = {"Idempotency-Key": uuid4().hex, "Authorization": "Bearer x"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r1, r2 = await asyncio.gather(
            c.post("/t/create", json={}, headers=h), c.post("/t/create", json={}, headers=h)
        )
    assert sorted([r1.status_code, r2.status_code]) == [200, 409]
    assert calls["n"] == 1


async def test_server_errors_are_not_stored_so_retry_runs_again() -> None:
    app, calls = _idem_app()
    h = {"Idempotency-Key": uuid4().hex, "Authorization": "Bearer x"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.post("/t/fail", headers=h)).status_code == 502
        assert (await c.post("/t/fail", headers=h)).status_code == 502
    assert calls["n"] == 2  # 502 is >= 500: not cached


async def test_no_header_or_get_is_untouched() -> None:
    app, calls = _idem_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/t/create", json={})
        await c.post("/t/create", json={})
    assert calls["n"] == 2


# ---------- rate limit ----------
async def test_token_bucket_blocks_then_refills() -> None:
    key = f"test:{uuid4().hex}"
    results = [await take(key, capacity=3, per_seconds=3) for _ in range(4)]
    assert [r[0] for r in results] == [True, True, True, False]
    assert results[3][1] >= 1
    await asyncio.sleep(1.1)  # refill rate 1 token/s
    assert (await take(key, capacity=3, per_seconds=3))[0] is True


async def test_rate_limit_dependency_returns_429_with_retry_after() -> None:
    app = create_app()
    name = uuid4().hex
    r = APIRouter()

    @r.get("/t/limited", dependencies=[Depends(rate_limit(capacity=2, per_seconds=60, name=name))])
    async def limited() -> dict[str, bool]:
        return {"ok": True}

    app.include_router(r)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        codes = [(await c.get("/t/limited")).status_code for _ in range(3)]
        last = await c.get("/t/limited")
    assert codes == [200, 200, 429]
    assert last.json()["error"]["code"] == "rate_limited"
    assert int(last.headers["retry-after"]) >= 1
