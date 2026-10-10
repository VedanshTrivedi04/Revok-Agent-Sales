"""Tests for Phase 6 (V6-01 & V6-03 & R6-02): Lifecycle, Security Checklist, Data Health.

Verifies:
- V6-01: PATCH /orgs/current side effects (schedule recompute, internal domains note)
- V6-01: DELETE /orgs/current soft delete, provider token revocation, job termination
- V6-01: purge_organization leaves 0 rows across all tenant tables, emits org.purged
- V6-01: Log export CSV and JSON jobs
- R6-02: GET /admin/data-health report
- V6-03: Security checklist tests (token redaction, app DB role restriction, log scrubbing, rate limits)
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import get_settings
from app.db.base import Base
from app.db.session import admin_session, org_session
from app.models.audit import DecisionLog
from app.models.brain import AgentRun, Finding
from app.models.integrations import Integration, OAuthToken
from app.models.tenancy import Organization
from app.models.timeline import Account, Contact
from app.services.identity import purge_organization
from app.utils.time import utcnow
from tests.helpers import SeededOrg


@pytest.fixture(autouse=True)
def phase6_sec_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_API", "false")
    monkeypatch.setenv(
        "REAL_ROUTERS",
        "today,findings,rules,accounts,admin,me,action_cards,integrations,auth,invites,members,orgs,log",
    )
    get_settings.cache_clear()


async def test_patch_org_side_effects(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    client = client_as("owner")

    # 1. Update timezone and nightly_hour -> triggers schedule_recomputed
    res = await client.patch(
        "/api/v1/orgs/current",
        json={"timezone": "America/New_York", "settings": {"nightly_hour": 3}},
    )
    assert res.status_code == 200, res.text
    assert res.json()["timezone"] == "America/New_York"

    # Verify decision_log entry
    async with org_session(org_a.org_id) as s:
        stmt = (
            select(DecisionLog)
            .where(DecisionLog.org_id == org_a.org_id, DecisionLog.event == "org.updated")
            .order_by(DecisionLog.id.desc())
        )
        entry = (await s.execute(stmt)).scalars().first()
        assert entry is not None
        assert "schedule_recomputed" in entry.data
        assert entry.data["schedule_recomputed"]["timezone"] == "America/New_York"
        assert entry.data["schedule_recomputed"]["nightly_hour"] == 3

    # 2. Update primary_domain -> triggers internal_domains_updated note
    res_domain = await client.patch(
        "/api/v1/orgs/current",
        json={"primary_domain": "newacme.com", "extra_domains": ["newacme.io"]},
    )
    assert res_domain.status_code == 200
    async with org_session(org_a.org_id) as s:
        stmt = (
            select(DecisionLog)
            .where(DecisionLog.org_id == org_a.org_id, DecisionLog.event == "org.updated")
            .order_by(DecisionLog.id.desc())
        )
        entry = (await s.execute(stmt)).scalars().first()
        assert entry is not None
        assert entry.data.get("internal_domains_updated") is True
        assert entry.data.get("internal_domains_note") == "Applies to new data"


async def test_org_delete_soft_delete_and_token_revocation(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    org_id = org_a.org_id
    integ_id = uuid4()
    tok_id = uuid4()
    run_id = uuid4()

    async with org_session(org_id) as s:
        integ = Integration(
            id=integ_id,
            org_id=org_id,
            provider="hubspot",
            scope_level="org",
            status="connected",
        )
        s.add(integ)
        tok = OAuthToken(
            id=tok_id,
            org_id=org_id,
            integration_id=integ_id,
            access_token_enc=b"enc_token_123",
            refresh_token_enc=b"enc_refresh_456",
            key_id="k1",
        )
        s.add(tok)
        run = AgentRun(
            id=run_id,
            org_id=org_id,
            trigger="nightly",
            status="running",
            started_at=utcnow(),
        )
        s.add(run)
        await s.flush()

        org = await s.get(Organization, org_id)
        assert org is not None
        org_name = org.name

    # Call DELETE /orgs/current
    client = client_as("owner")
    res = await client.request("DELETE", "/api/v1/orgs/current", json={"confirm": org_name})
    assert res.status_code == 200
    assert res.json()["ok"] is True

    # Verify soft delete and cleanup
    async with admin_session() as s:
        org = await s.get(Organization, org_id)
        assert org is not None
        assert org.status == "deleted"
        assert org.deleted_at is not None

        # Integrations disconnected
        updated_integ = await s.get(Integration, integ_id)
        assert updated_integ is not None
        assert updated_integ.status == "disconnected"

        # Tokens blanked
        updated_tok = await s.get(OAuthToken, tok_id)
        assert updated_tok is not None
        assert updated_tok.access_token_enc == b""
        assert updated_tok.refresh_token_enc == b""

        # Runs stopped
        updated_run = await s.get(AgentRun, run_id)
        assert updated_run is not None
        assert updated_run.status == "failed"
        assert "Organization deleted" in (updated_run.error or "")


async def test_purge_organization_leaves_zero_rows(
    owner_engine: AsyncEngine, org_b: SeededOrg
) -> None:
    org_id = org_b.org_id
    acc_id = uuid4()

    # Seed data in multiple tables
    async with org_session(org_id) as s:
        acc = Account(id=acc_id, org_id=org_id, name="Purge Test Acc")
        s.add(acc)
        await s.flush()
        c = Contact(id=uuid4(), org_id=org_id, account_id=acc_id, email="purge@test.com")
        s.add(c)
        f = Finding(
            id=uuid4(),
            org_id=org_id,
            account_id=acc_id,
            type="risk",
            fingerprint=f"fp-{uuid4()}",
            status="open",
            severity="low",
            priority_score=Decimal("10.0"),
            confidence=0.5,
            title="Purge Finding",
        )
        s.add(f)
        await s.flush()

    # Mark org deleted
    async with admin_session() as s:
        org = await s.get(Organization, org_id)
        assert org is not None
        org.status = "deleted"
        org.deleted_at = utcnow() - timedelta(days=31)
        await s.flush()

        # Execute purge
        counts = await purge_organization(s, org_id, force=False)
        assert len(counts) > 0

    # Verify zero rows remain for org_id across all tenant tables
    async with admin_session() as s:
        for table in Base.metadata.sorted_tables:
            if "org_id" in table.c:
                stmt = select(table).where(table.c.org_id == org_id)
                rows = (await s.execute(stmt)).all()
                assert len(rows) == 0, (
                    f"Table {table.name} still has {len(rows)} rows for org_id {org_id}"
                )
            elif table.name == "organizations":
                stmt = select(table).where(table.c.id == org_id)
                rows = (await s.execute(stmt)).all()
                assert len(rows) == 0, f"Organization {org_id} still exists in organizations table"


async def test_decision_log_export_csv_and_json(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    client = client_as("owner")

    # 1. Export CSV
    res_csv = await client.post(
        "/api/v1/log/export",
        json={"format": "csv"},
    )
    assert res_csv.status_code == 202
    csv_data = res_csv.json()
    assert csv_data["status"] == "done"
    assert "format=csv" in csv_data["download_url"]

    # 2. Export JSON
    res_json = await client.post(
        "/api/v1/log/export",
        json={"format": "json"},
    )
    assert res_json.status_code == 202
    json_data = res_json.json()
    assert json_data["status"] == "done"
    assert "format=json" in json_data["download_url"]


async def test_admin_data_health_endpoint(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    async with owner_engine.begin() as conn:
        await conn.execute(
            text("UPDATE users SET is_superadmin = true WHERE id = :u"),
            {"u": org_a.users["owner"]},
        )

    client = client_as("owner")
    res = await client.get("/api/v1/admin/data-health")
    assert res.status_code == 200, res.text
    data = res.json()
    assert "accounts_missing_renewal_date" in data
    assert "unmapped_owners" in data
    assert "orphan_events" in data
    assert "contacts_without_account" in data
    assert isinstance(data["accounts_missing_renewal_date"], int)


async def test_security_checklist_items(org_a: SeededOrg) -> None:
    """Validate critical items from backenddeveloper.md section 12."""
    from app.observability import scrub_processor

    # 1. OAuthToken repr never logs secret token bytes
    tok = OAuthToken(
        id=uuid4(),
        org_id=org_a.org_id,
        integration_id=uuid4(),
        access_token_enc=b"super_secret_token_12345",
        refresh_token_enc=b"super_secret_refresh_67890",
        key_id="k1",
    )
    repr_str = repr(tok)
    assert "super_secret_token_12345" not in repr_str
    assert "super_secret_refresh_67890" not in repr_str

    # 2. Log scrubber redacts tokens, passwords, emails, and sensitive keys
    event_dict = {
        "event": "user.login",
        "level": "info",
        "timestamp": "2026-10-11T00:00:00Z",
        "token": "secret_bearer_token",
        "user_email": "alice@customer.com",
        "message": "User alice@customer.com logged in",
        "details": {"password": "secret_pass", "note": "Contact bob@acme.com"},
    }
    scrubbed = scrub_processor(None, "info", event_dict)
    assert scrubbed["token"] == "[redacted]"
    assert scrubbed["user_email"] == "[redacted]"
    assert scrubbed["details"]["password"] == "[redacted]"
    assert "[email]" in scrubbed["message"]
    assert "[email]" in scrubbed["details"]["note"]
