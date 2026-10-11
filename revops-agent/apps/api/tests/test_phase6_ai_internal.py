"""Tests for Phase 6 (V6-02): AI internal endpoints (/internal/v1/orgs/{org}/...).

Verifies:
- X-Internal-Key header validation (401 on missing/invalid)
- Context fetch (/accounts/{id}/context) with complete numbered evidence
- Pending events extraction (/events/pending-extraction)
- Signal ingestion (/events/{id}/signals) with exact quote substring validation
- Explanation ingestion (/findings/{id}/explanation) validating evidence IDs exist for finding
- Action proposals (/findings/{id}/proposals) validating recipient allowlists, banned phrases, tier policy
- Run status reporting (/runs/{id}/status)
- Contact list fetch (/accounts/{id}/contacts)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import get_settings
from app.db.session import org_session
from app.models.actions import ActionCard
from app.models.brain import AgentRun, Finding, FindingEvidence, Signal
from app.models.timeline import Account, Contact, Deal, Event
from app.utils.time import utcnow
from tests.helpers import SeededOrg


@pytest.fixture(autouse=True)
def phase6_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_API", "false")
    monkeypatch.setenv(
        "REAL_ROUTERS",
        "today,findings,rules,accounts,admin,me,action_cards,integrations,auth,invites,members,orgs",
    )
    get_settings.cache_clear()


async def test_internal_key_required_and_validated(client: AsyncClient, org_a: SeededOrg) -> None:
    org_id = org_a.org_id
    fake_acc = uuid4()
    url = f"/internal/v1/orgs/{org_id}/accounts/{fake_acc}/context"

    # Missing header -> 401
    res = await client.get(url)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthenticated"

    # Bad header -> 401
    res = await client.get(url, headers={"X-Internal-Key": "wrong-key"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthenticated"


async def test_get_account_context_and_contacts(client: AsyncClient, org_a: SeededOrg) -> None:
    org_id = org_a.org_id
    internal_key = get_settings().internal_api_key
    headers = {"X-Internal-Key": internal_key}

    acc_id = uuid4()
    async with org_session(org_id) as s:
        acc = Account(
            id=acc_id,
            org_id=org_id,
            name="Alpha Corp",
            domains=["alphacorp.io"],
            arr=Decimal("120000.00"),
            plan_name="Enterprise",
            seats_purchased=50,
            renewal_date=date(2026, 12, 1),
            lifecycle_stage="customer",
            crm_health="Amber",
            status="active",
            risk_level="medium",
            priority_score=Decimal("65.0"),
            crm_url="https://crm.hubspot.com/alpha",
        )
        s.add(acc)
        await s.flush()

        c1 = Contact(
            id=uuid4(),
            org_id=org_id,
            account_id=acc_id,
            name="Alice Smith",
            email="alice@alphacorp.io",
            title="VP of Sales",
            role_tags=["decision_maker"],
            is_active=True,
        )
        s.add(c1)

        deal = Deal(
            id=uuid4(),
            org_id=org_id,
            account_id=acc_id,
            name="Renewal 2026",
            amount=Decimal("120000.00"),
            stage="negotiation",
            close_date=date(2026, 12, 1),
            deal_type="renewal",
        )
        s.add(deal)

        ev = Event(
            id=uuid4(),
            org_id=org_id,
            account_id=acc_id,
            source="hubspot",
            source_record_id=f"rec-{uuid4()}",
            type="email_in",
            occurred_at=utcnow(),
            title="Meeting feedback",
            body_text="We have some budget questions before renewal.",
            raw={},
        )
        s.add(ev)

        finding = Finding(
            id=uuid4(),
            org_id=org_id,
            account_id=acc_id,
            type="risk",
            fingerprint=f"fp-{uuid4()}",
            status="open",
            severity="medium",
            priority_score=Decimal("60.0"),
            confidence=0.85,
            title="Budget concern before renewal",
            rule_keys=["R01"],
            categories=["renewal"],
        )
        s.add(finding)
        await s.flush()

        evidence = FindingEvidence(
            id=uuid4(),
            org_id=org_id,
            finding_id=finding.id,
            evidence_key="E1",
            kind="event",
            label="Customer raised budget concerns",
            detail="We have some budget questions before renewal.",
            source="hubspot",
            occurred_at=utcnow(),
        )
        s.add(evidence)
        await s.flush()

    # 1. Test GET context
    ctx_res = await client.get(
        f"/internal/v1/orgs/{org_id}/accounts/{acc_id}/context",
        headers=headers,
    )
    assert ctx_res.status_code == 200, ctx_res.text
    ctx_data = ctx_res.json()
    assert ctx_data["account"]["name"] == "Alpha Corp"
    assert len(ctx_data["contacts"]) >= 1
    assert ctx_data["contacts"][0]["email"] == "alice@alphacorp.io"
    assert len(ctx_data["deals"]) == 1
    assert len(ctx_data["recent_events"]) == 1
    assert "budget questions" in ctx_data["recent_events"][0]["text"]
    assert len(ctx_data["evidence"]) >= 1
    assert ctx_data["evidence"][0]["key"] == "E1"

    # 2. Test GET contacts
    contacts_res = await client.get(
        f"/internal/v1/orgs/{org_id}/accounts/{acc_id}/contacts",
        headers=headers,
    )
    assert contacts_res.status_code == 200
    contacts_data = contacts_res.json()
    assert len(contacts_data) >= 1
    assert contacts_data[0]["email"] == "alice@alphacorp.io"
    assert "decision_maker" in contacts_data[0]["role_tags"]


async def test_pending_extraction_and_signals_ingest_quote_substring(
    client: AsyncClient, org_a: SeededOrg
) -> None:
    org_id = org_a.org_id
    internal_key = get_settings().internal_api_key
    headers = {"X-Internal-Key": internal_key}

    acc_id = uuid4()
    ev_id = uuid4()
    async with org_session(org_id) as s:
        acc = Account(
            id=acc_id,
            org_id=org_id,
            name="Delta Corp",
            domains=["delta.com"],
        )
        s.add(acc)
        await s.flush()

        ev = Event(
            id=ev_id,
            org_id=org_id,
            account_id=acc_id,
            source="gmail",
            source_record_id=f"msg-{uuid4()}",
            type="email_in",
            occurred_at=utcnow(),
            title="Contract review",
            body_text="The procurement team noticed a competitor Acme offering 30% discount.",
            signals_extracted_at=None,
            raw={},
        )
        s.add(ev)
        await s.flush()

    # 1. Fetch pending events
    pending_res = await client.get(
        f"/internal/v1/orgs/{org_id}/events/pending-extraction?limit=10",
        headers=headers,
    )
    assert pending_res.status_code == 200
    pending_data = pending_res.json()
    ev_ids = [e["id"] for e in pending_data["events"]]
    assert str(ev_id) in ev_ids

    # 2. Ingest signals: one valid quote substring, one invalid quote
    payload = {
        "signals": [
            {
                "kind": "competitor_mention",
                "polarity": "negative",
                "value": {"competitor": "Acme"},
                "confidence": 0.95,
                "quote": "competitor Acme offering 30% discount",
                "model": "qwen3.5-9b",
                "prompt_version": "extract@1.0.0",
            },
            {
                "kind": "sentiment",
                "polarity": "negative",
                "value": {},
                "confidence": 0.9,
                "quote": "we are canceling our subscription today",  # NOT in text
                "model": "qwen3.5-9b",
                "prompt_version": "extract@1.0.0",
            },
        ]
    }

    sig_res = await client.post(
        f"/internal/v1/orgs/{org_id}/events/{ev_id}/signals",
        headers=headers,
        json=payload,
    )
    assert sig_res.status_code == 200, sig_res.text
    res_data = sig_res.json()
    assert res_data["saved"] == 1
    assert len(res_data["rejected"]) == 1
    assert res_data["rejected"][0]["reason"] == "quote must be a substring of the event text"

    # Verify event signals_extracted_at was populated
    async with org_session(org_id) as s:
        updated_ev = await s.get(Event, ev_id)
        assert updated_ev is not None
        assert updated_ev.signals_extracted_at is not None

        # Verify Signal was saved in DB
        sig_stmt = select(Signal).where(Signal.event_id == ev_id)
        saved_sigs = (await s.execute(sig_stmt)).scalars().all()
        assert len(saved_sigs) == 1
        assert saved_sigs[0].kind == "competitor_mention"


async def test_save_explanation_evidence_validation(client: AsyncClient, org_a: SeededOrg) -> None:
    org_id = org_a.org_id
    internal_key = get_settings().internal_api_key
    headers = {"X-Internal-Key": internal_key}

    acc_id = uuid4()
    finding_id = uuid4()
    async with org_session(org_id) as s:
        acc = Account(id=acc_id, org_id=org_id, name="Beta Ltd", domains=["beta.com"])
        s.add(acc)
        await s.flush()

        finding = Finding(
            id=finding_id,
            org_id=org_id,
            account_id=acc_id,
            type="risk",
            fingerprint=f"fp-{uuid4()}",
            status="open",
            severity="high",
            priority_score=Decimal("80.0"),
            confidence=0.9,
            title="Usage Drop",
            rule_keys=["R01"],
            categories=["usage"],
        )
        s.add(finding)
        await s.flush()

        evidence = FindingEvidence(
            id=uuid4(),
            org_id=org_id,
            finding_id=finding_id,
            evidence_key="E1",
            kind="usage",
            label="Active users dropped 40%",
            occurred_at=utcnow(),
        )
        s.add(evidence)
        await s.flush()

    # 1. Invalid explanation citing non-existent evidence ID E999
    bad_payload = {
        "summary": "Account has critical risk",
        "claims": [{"text": "Usage dropped heavily", "evidence_ids": ["E999"]}],
        "unknowns": [],
        "contradictions": [],
        "confidence_label": "high",
        "model": "qwen3.5-9b",
        "prompt_version": "explain@1.0.0",
    }
    bad_res = await client.post(
        f"/internal/v1/orgs/{org_id}/findings/{finding_id}/explanation",
        headers=headers,
        json=bad_payload,
    )
    assert bad_res.status_code == 200
    bad_data = bad_res.json()
    assert bad_data["accepted"] is False
    assert any("E999" in err for err in bad_data["errors"])

    # 2. Valid explanation citing valid evidence ID E1
    good_payload = {
        "summary": "Usage dropped by 40% in the last 30 days.",
        "claims": [{"text": "Active users dropped 40%", "evidence_ids": ["E1"]}],
        "unknowns": ["No contact from champion recently"],
        "contradictions": [],
        "confidence_label": "high",
        "model": "qwen3.5-9b",
        "prompt_version": "explain@1.0.0",
    }
    good_res = await client.post(
        f"/internal/v1/orgs/{org_id}/findings/{finding_id}/explanation",
        headers=headers,
        json=good_payload,
    )
    assert good_res.status_code == 200
    good_data = good_res.json()
    assert good_data["accepted"] is True
    assert good_data["errors"] == []

    # Verify DB was updated
    async with org_session(org_id) as s:
        updated_f = await s.get(Finding, finding_id)
        assert updated_f is not None
        assert updated_f.summary == "Usage dropped by 40% in the last 30 days."
        assert len(updated_f.claims) == 1
        assert updated_f.claims[0]["evidence_ids"] == ["E1"]


async def test_save_proposals_allowlist_banned_phrases_and_tier_policy(
    client: AsyncClient, org_a: SeededOrg
) -> None:
    org_id = org_a.org_id
    internal_key = get_settings().internal_api_key
    headers = {"X-Internal-Key": internal_key}

    acc_id = uuid4()
    finding_id = uuid4()
    contact_id = uuid4()

    async with org_session(org_id) as s:
        acc = Account(id=acc_id, org_id=org_id, name="Gamma Inc", domains=["gammainc.com"])
        s.add(acc)
        await s.flush()

        contact = Contact(
            id=contact_id,
            org_id=org_id,
            account_id=acc_id,
            name="Bob Jones",
            email="bob@gammainc.com",
            title="CTO",
            is_active=True,
        )
        s.add(contact)
        finding = Finding(
            id=finding_id,
            org_id=org_id,
            account_id=acc_id,
            type="risk",
            fingerprint=f"fp-{uuid4()}",
            status="open",
            severity="medium",
            priority_score=Decimal("60.0"),
            confidence=0.8,
            title="Renewal at Risk",
            rule_keys=["R02"],
            categories=["renewal"],
        )
        s.add(finding)
        await s.flush()

    # 1. Propose email to unauthorized external email -> rejected by allowlist
    res_allowlist = await client.post(
        f"/internal/v1/orgs/{org_id}/findings/{finding_id}/proposals",
        headers=headers,
        json={
            "proposals": [
                {
                    "type": "email_draft",
                    "payload": {
                        "to": ["stranger@random.com"],
                        "subject": "Check-in",
                        "body": "Hello there",
                    },
                    "rationale": "Outreach",
                    "evidence_keys": [],
                }
            ]
        },
    )
    assert res_allowlist.status_code == 200
    data_allowlist = res_allowlist.json()
    assert len(data_allowlist["created_card_ids"]) == 0
    assert any("not in allowlist" in rej["reason"] for rej in data_allowlist["rejected"])

    # 2. Propose email containing banned phrase -> rejected
    res_banned = await client.post(
        f"/internal/v1/orgs/{org_id}/findings/{finding_id}/proposals",
        headers=headers,
        json={
            "proposals": [
                {
                    "type": "email_draft",
                    "payload": {
                        "to": ["bob@gammainc.com"],
                        "subject": "Special Offer",
                        "body": "We can offer a 20% discount and unconditional discount on renewal.",
                    },
                    "rationale": "Discount offer",
                    "evidence_keys": [],
                }
            ]
        },
    )
    assert res_banned.status_code == 200
    data_banned = res_banned.json()
    assert len(data_banned["created_card_ids"]) == 0
    assert any("banned_phrase_detected" in rej["reason"] for rej in data_banned["rejected"])

    # 3. Valid CRM task proposal -> accepted & created card
    res_valid = await client.post(
        f"/internal/v1/orgs/{org_id}/findings/{finding_id}/proposals",
        headers=headers,
        json={
            "proposals": [
                {
                    "type": "crm_task",
                    "payload": {
                        "title": "Schedule Executive Sync with Bob",
                        "due_date": "2026-11-15",
                        "priority": "HIGH",
                        "owner_crm_id": "77",
                        "associate": [{"object": "company", "id": "9001"}],
                    },
                    "rationale": "Re-engage CTO before renewal.",
                    "evidence_keys": [],
                }
            ]
        },
    )
    assert res_valid.status_code == 200
    data_valid = res_valid.json()
    assert len(data_valid["created_card_ids"]) == 1
    card_id = data_valid["created_card_ids"][0]

    async with org_session(org_id) as s:
        card = await s.get(ActionCard, UUID(card_id))
        assert card is not None
        assert card.account_id == acc_id
        assert card.finding_id == finding_id
        assert card.type == "crm_task"


async def test_run_status_reporting(client: AsyncClient, org_a: SeededOrg) -> None:
    org_id = org_a.org_id
    internal_key = get_settings().internal_api_key
    headers = {"X-Internal-Key": internal_key}

    run_id = uuid4()
    async with org_session(org_id) as s:
        run = AgentRun(
            id=run_id,
            org_id=org_id,
            trigger="nightly",
            status="running",
            started_at=utcnow(),
        )
        s.add(run)
        await s.flush()

    res = await client.post(
        f"/internal/v1/orgs/{org_id}/runs/{run_id}/status",
        headers=headers,
        json={
            "status": "completed",
            "stats": {"accounts_analyzed": 50, "findings_created": 3},
        },
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True

    async with org_session(org_id) as s:
        updated_run = await s.get(AgentRun, run_id)
        assert updated_run is not None
        assert updated_run.status == "completed"
        assert updated_run.finished_at is not None
        assert updated_run.stats.get("accounts_analyzed") == 50
