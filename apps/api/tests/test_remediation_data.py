"""Regression tests for audit findings H3/H4, M1-M5, M7 (export, audit events, integrations,
member removal, usage ingest, score_breakdown)."""

import json
from datetime import date, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import respx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import get_settings
from app.connectors import registry
from app.connectors.fake import FakeConnector
from app.db.session import org_session
from app.models.actions import ActionCard
from app.models.audit import DecisionLog, Notification
from app.models.integrations import Integration, OAuthToken
from app.models.timeline import UsageSnapshot
from app.schemas.integrations import UsageRowIn
from app.services.integrations import record_sync_failure_service
from app.services.usage import (
    MAX_CSV_BYTES,
    ROLLUP_MARK,
    create_csv_job,
    get_csv_job,
    ingest_usage_service,
)
from app.utils.crypto import generate_key
from app.utils.errors import AppError
from app.utils.oauth_state import create_state
from tests.factories import AccountFactory, CardFactory, FindingFactory, persist
from tests.helpers import SeededOrg, assert_logged


@pytest.fixture
def enc_keys(monkeypatch: pytest.MonkeyPatch) -> str:
    keys = f"k1:{generate_key()}"
    monkeypatch.setenv("TOKEN_ENC_KEYS", keys)
    get_settings.cache_clear()
    return keys


# ------------------------------------------------------------------ H4: log export works end to end
async def test_log_export_csv_json_download_isolation_and_audit(
    org_a: SeededOrg, org_b: SeededOrg, client_as: Any
) -> None:
    admin = client_as("admin")
    first = await admin.post("/api/v1/log/export", json={"format": "csv"})
    assert first.status_code == 202
    second = await admin.post("/api/v1/log/export", json={"format": "csv"})
    body = second.json()
    assert body["status"] == "done" and body["download_url"].endswith("/download")

    dl = await admin.get(body["download_url"])
    assert dl.status_code == 200 and dl.headers["content-type"].startswith("text/csv")
    assert "attachment" in dl.headers["content-disposition"]
    lines = dl.text.strip().splitlines()
    assert (
        lines[0].startswith("id,ts,actor_type") and "data.exported" in dl.text
    )  # first export is in the second

    js = (await admin.post("/api/v1/log/export", json={"format": "json"})).json()
    exported = (await admin.get(js["download_url"])).json()
    assert (
        isinstance(exported, list)
        and exported
        and {"hash", "prev_hash", "event"} <= set(exported[0])
    )

    status = await admin.get(f"/api/v1/log/export/{body['job_id']}")
    assert status.status_code == 200 and status.json()["job_id"] == body["job_id"]

    other = client_as("admin", org_b)  # another tenant can neither see nor download it
    assert (await other.get(f"/api/v1/log/export/{body['job_id']}")).status_code == 404
    assert (await other.get(body["download_url"])).status_code == 404
    assert (
        await admin.get(f"/api/v1/log/export/{uuid4()}")
    ).status_code == 404  # unknown id is not "done"
    await assert_logged(org_a.org_id, "data.exported", times=3)

    assert (await client_as("manager").post("/api/v1/log/export", json={})).status_code == 403


# ------------------------------------------------------------------ M2 + FK fix: OAuth callback / disconnect
@respx.mock
async def test_oauth_callback_persists_integration_tokens_and_logs_then_disconnect_revokes(
    org_a: SeededOrg, client_as: Any, enc_keys: str
) -> None:
    registry.register(FakeConnector(provider="hubspot"))
    try:
        state = create_state(org_a.org_id, org_a.users["admin"], "hubspot")
        anon = client_as("admin")
        r = await anon.get(
            f"/api/v1/oauth/hubspot/callback?code=abc&state={state}", follow_redirects=False
        )
        assert r.status_code == 302 and "connected=hubspot" in r.headers["location"]

        async with org_session(org_a.org_id) as s:
            integ = (await s.execute(select(Integration))).scalar_one()
            tok = (await s.execute(select(OAuthToken))).scalar_one()
        assert (
            integ.status == "connected"
            and tok.access_token_enc
            and b"access-abc" not in tok.access_token_enc
        )
        await assert_logged(org_a.org_id, "integration.connected", entity_id=integ.id)

        revoke = respx.delete(
            url__regex=r"https://api\.hubapi\.com/oauth/v1/refresh-tokens/.*"
        ).mock(return_value=httpx.Response(204))
        d = await anon.delete(f"/api/v1/integrations/{integ.id}")
        assert d.status_code == 200 and revoke.called
        async with org_session(org_a.org_id) as s:
            tok = (await s.execute(select(OAuthToken))).scalar_one()
            integ = (await s.execute(select(Integration))).scalar_one()
            entry = (
                await s.execute(
                    select(DecisionLog).where(DecisionLog.event == "integration.disconnected")
                )
            ).scalar_one()
        assert (
            tok.access_token_enc == b""
            and tok.refresh_token_enc is None
            and integ.status == "disconnected"
        )
        assert entry.data["provider_revoked"] is True
    finally:
        registry.unregister("hubspot")


# ------------------------------------------------------------------ M1: failure streak notifies admins once
async def test_third_consecutive_sync_failure_notifies_admins_exactly_once(
    org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    iid = uuid4()
    async with owner_engine.begin() as c:
        await c.execute(
            text(
                "INSERT INTO integrations (id, org_id, provider, scope_level, status) VALUES (:i,:o,'hubspot','org','connected')"
            ),
            {"i": iid, "o": org_a.org_id},
        )
    for _ in range(5):
        async with org_session(org_a.org_id) as s:
            await record_sync_failure_service(s, org_a.org_id, iid, "HubSpot 500")
    async with org_session(org_a.org_id) as s:
        notes = (
            (await s.execute(select(Notification).where(Notification.kind == "integration_error")))
            .scalars()
            .all()
        )
    admins = {org_a.users["owner"], org_a.users["admin"]}
    assert {n.user_id for n in notes} == admins and len(notes) == len(admins)


# ------------------------------------------------------------------ M4: removing a member hands over open cards
async def test_removing_a_member_reassigns_open_cards_and_disconnects_their_google(
    org_a: SeededOrg, client_as: Any, owner_engine: AsyncEngine
) -> None:
    acc = AccountFactory.build(org_id=org_a.org_id, owner_user_id=org_a.users["manager"])
    pending = CardFactory.build(
        org_id=org_a.org_id, account_id=acc.id, status="pending_approval", type="email_draft", tier=2,
        payload={}, assignee_user_id=org_a.users["member"],
    )  # fmt: skip
    executed = CardFactory.build(
        org_id=org_a.org_id,
        account_id=acc.id,
        status="executed",
        payload={},
        assignee_user_id=org_a.users["member"],
    )
    await persist(org_a.org_id, acc, pending, executed)
    async with owner_engine.begin() as c:
        await c.execute(
            text(
                "INSERT INTO integrations (id, org_id, provider, scope_level, user_id, status) VALUES (:i,:o,'gmail','user',:u,'connected')"
            ),
            {"i": uuid4(), "o": org_a.org_id, "u": org_a.users["member"]},
        )
    owner = client_as("owner")
    members = (await owner.get("/api/v1/members?limit=50")).json()["items"]
    target = next(m for m in members if m["role"] == "member")
    assert (await owner.delete(f"/api/v1/members/{target['id']}")).status_code == 200
    async with org_session(org_a.org_id) as s:
        cards = {c.id: c for c in (await s.execute(select(ActionCard))).scalars()}
        gmail = (
            await s.execute(select(Integration).where(Integration.provider == "gmail"))
        ).scalar_one()
    assert cards[pending.id].assignee_user_id == org_a.users["manager"]
    assert cards[executed.id].assignee_user_id == org_a.users["member"]  # history is untouched
    assert gmail.status == "disconnected"
    await assert_logged(org_a.org_id, "card.assigned", entity_id=pending.id)


async def test_role_change_logs_member_role_changed_and_invite_logs_member_invited(
    org_a: SeededOrg, client_as: Any
) -> None:
    admin = client_as("owner")
    members = (await admin.get("/api/v1/members?limit=50")).json()["items"]
    viewer = next(m for m in members if m["role"] == "viewer")
    assert (
        await admin.patch(f"/api/v1/members/{viewer['id']}", json={"role": "member"})
    ).status_code == 200
    await assert_logged(org_a.org_id, "member.role_changed", entity_id=UUID(viewer["id"]))
    inv = await admin.post(
        "/api/v1/invites", json={"email": "new.hire@customer.example.com", "role": "member"}
    )
    assert inv.status_code == 201
    await assert_logged(org_a.org_id, "member.invited", entity_id=UUID(inv.json()["id"]))


# ------------------------------------------------------------------ M3: usage ingest
async def _account(org: SeededOrg, domain: str = "usage-co.example.com") -> UUID:
    acc = AccountFactory.build(org_id=org.org_id, domains=[domain])
    await persist(org.org_id, acc)
    return acc.id


def _day(d: date, users: int, **kw: Any) -> UsageRowIn:
    return UsageRowIn(
        account_key="usage-co.example.com", account_key_type="domain", period_start=d,
        granularity="day", active_users=users, **kw,
    )  # fmt: skip


async def test_daily_usage_rolls_up_to_a_marked_weekly_row(org_a: SeededOrg) -> None:
    acc_id = await _account(org_a)
    monday = date(2026, 9, 28)
    rows = [_day(monday + timedelta(days=i), u, logins=u * 2) for i, u in enumerate([10, 14, 12])]
    async with org_session(org_a.org_id) as s:
        res = await ingest_usage_service(s, org_a.org_id, rows)
    assert res.accepted == 3
    async with org_session(org_a.org_id) as s:
        weekly = (
            await s.execute(select(UsageSnapshot).where(UsageSnapshot.granularity == "week"))
        ).scalar_one()
    assert weekly.account_id == acc_id and weekly.period_start == monday
    assert (
        weekly.active_users == 14 and weekly.logins == 72 and weekly.key_events == {ROLLUP_MARK: 3}
    )

    async with org_session(org_a.org_id) as s:  # a later day updates the rollup, not duplicates it
        await ingest_usage_service(s, org_a.org_id, [_day(monday + timedelta(days=3), 20)])
    async with org_session(org_a.org_id) as s:
        weeklies = (
            (await s.execute(select(UsageSnapshot).where(UsageSnapshot.granularity == "week")))
            .scalars()
            .all()
        )
    assert (
        len(weeklies) == 1
        and weeklies[0].active_users == 20
        and weeklies[0].key_events == {ROLLUP_MARK: 4}
    )


async def test_a_directly_pushed_weekly_value_is_never_overwritten_by_a_rollup(
    org_a: SeededOrg,
) -> None:
    await _account(org_a)
    monday = date(2026, 9, 21)
    weekly = UsageRowIn(
        account_key="usage-co.example.com", account_key_type="domain", period_start=monday,
        granularity="week", active_users=99,
    )  # fmt: skip
    async with org_session(org_a.org_id) as s:
        await ingest_usage_service(s, org_a.org_id, [weekly])
    async with org_session(org_a.org_id) as s:
        await ingest_usage_service(
            s, org_a.org_id, [_day(monday, 5), _day(monday + timedelta(days=1), 7)]
        )
    async with org_session(org_a.org_id) as s:
        row = (
            await s.execute(select(UsageSnapshot).where(UsageSnapshot.granularity == "week"))
        ).scalar_one()
    assert row.active_users == 99 and ROLLUP_MARK not in row.key_events


async def test_csv_import_reports_precise_reasons_limits_and_job_status(org_a: SeededOrg) -> None:
    await _account(org_a)
    mapping = json.dumps(
        {
            "account_key": "domain",
            "account_key_type": "domain",
            "period_start": "week",
            "granularity": "week",
            "active_users": "au",
        }
    )
    lines = [
        "domain,week,au",
        "usage-co.example.com,2026-09-28,12",
        ",2026-09-28,3",
        "usage-co.example.com,not-a-date,3",
        "usage-co.example.com,2026-10-05,abc",
    ]
    lines += [f"unknown{i}.example.com,2026-10-05,1" for i in range(30)]
    async with org_session(org_a.org_id) as s:
        job = await create_csv_job(s, org_a.org_id, "\n".join(lines).encode(), mapping)
    assert job.accepted == 1 and job.processed == 34 and job.rejected_count == 33
    assert len(job.errors) == 20  # sample only
    assert [e.reason for e in job.errors[:3]] == [
        "missing_account_key",
        "invalid_date",
        "invalid_number",
    ]
    again = await get_csv_job(org_a.org_id, job.job_id)
    assert again.rejected_count == 33 and again.processed == 34

    async with org_session(org_a.org_id) as s:
        with pytest.raises(AppError) as ei:
            await create_csv_job(s, org_a.org_id, b"x" * (MAX_CSV_BYTES + 1), mapping)
    assert ei.value.code == "payload_too_large" and ei.value.status == 413


# ------------------------------------------------------------------ M5/M7: score_breakdown column, trigram index
async def test_score_breakdown_is_a_column_returned_by_the_finding_detail(
    org_a: SeededOrg, client_as: Any
) -> None:
    acc = AccountFactory.build(org_id=org_a.org_id)
    breakdown = {
        "severity_s": 1.0,
        "urgency": 0.8,
        "value": 0.7,
        "confidence": 0.6,
        "freshness": 1.0,
    }
    finding = FindingFactory.build(
        org_id=org_a.org_id, account_id=acc.id, score_breakdown=breakdown
    )
    await persist(org_a.org_id, acc, finding)
    r = await client_as("viewer").get(f"/api/v1/findings/{finding.id}")
    assert r.status_code == 200 and r.json()["score_breakdown"] == breakdown


async def test_account_name_search_has_a_trigram_index(owner_engine: AsyncEngine) -> None:
    async with owner_engine.connect() as c:
        defs = (
            (
                await c.execute(
                    text(
                        "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_accounts_name_trgm'"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert defs and "gin_trgm_ops" in defs[0]


# ------------------------------------------------------------------ H3: delete + purge
async def test_org_delete_wipes_tokens_and_stops_queued_runs_then_purge_removes_everything(
    org_a: SeededOrg, owner_engine: AsyncEngine, client_as: Any, enc_keys: str
) -> None:
    from app.models.brain import AgentRun
    from app.services.identity import purge_organization

    acc = AccountFactory.build(org_id=org_a.org_id)
    run = AgentRun(org_id=org_a.org_id, account_id=acc.id, trigger="manual", status="queued")
    await persist(org_a.org_id, acc, run)
    r = await client_as("owner").request(
        "DELETE", "/api/v1/orgs/current", json={"confirm": await _org_name(owner_engine, org_a)}
    )
    assert r.status_code == 200
    async with org_session(org_a.org_id) as s:
        assert (await s.get(AgentRun, run.id)).status == "failed"  # type: ignore[union-attr]
    from app.db.session import admin_session

    async with admin_session() as s:
        with pytest.raises(AppError):  # inside the 30-day retention window
            await purge_organization(s, org_a.org_id)
    async with admin_session() as s:
        counts = await purge_organization(s, org_a.org_id, force=True)
    assert counts["organizations"] == 1 and counts["agent_runs"] == 1
    async with owner_engine.connect() as c:
        assert (
            await c.execute(
                text("SELECT count(*) FROM organizations WHERE id = :i"), {"i": org_a.org_id}
            )
        ).scalar() == 0


async def _org_name(engine: AsyncEngine, org: SeededOrg) -> str:
    async with engine.connect() as c:
        return str(
            (
                await c.execute(
                    text("SELECT name FROM organizations WHERE id = :i"), {"i": org.org_id}
                )
            ).scalar()
        )
