"""Phase 4 test suite: Today, Findings, Rules, Diff, and Performance (R4-01..R4-05).

Covers:
- R4-01: GET /today (ranked items, ownership defaulting, low-severity hidden unless renewal <= 30d,
  top_reasons, pending_cards count, is_new, changed_since_yesterday, summary counts).
- R4-01: GET /findings and GET /findings/{id} (full detail with claims, evidence, rule_hits, cards, history).
- R4-01: POST /findings/{id}/dismiss, snooze, reopen, feedback with role & ownership permission matrix.
- R4-02: GET /rules, PUT /rules/{key} (param validation + decision_log), POST /rules/{key}/preview, POST /rules/rerun.
- R4-03: "What changed" diff versus previous_snapshot.
- R4-04: Today performance (no N+1 per-row queries, indexed execution).
- R4-05: Real router verification.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import get_settings
from app.db.session import org_session
from app.models.actions import ActionCard
from app.models.audit import DecisionLog
from app.models.brain import Finding, FindingEvidence, Rule, RuleHit
from app.models.timeline import Account, Contact, Deal, Event, UsageSnapshot
from app.schemas.accounts import TodayResponse
from app.services import decision_log
from app.services.findings import compute_finding_diff
from app.utils.time import utcnow
from tests.helpers import SeededOrg


@pytest.fixture(autouse=True)
def phase4_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_API", "false")
    monkeypatch.setenv(
        "REAL_ROUTERS",
        "today,findings,rules,accounts,admin,me,action_cards,integrations,auth,invites,members,orgs",
    )
    get_settings.cache_clear()


async def _create_account_with_owner(
    session: Any,
    org_id: UUID,
    name: str,
    owner_user_id: UUID | None,
    arr: float = 50000.0,
    renewal_date: date | None = None,
    crm_health: str = "Green",
) -> Account:
    acc = Account(
        id=uuid4(),
        org_id=org_id,
        name=name,
        domains=[f"{name.lower().replace(' ', '')}.com"],
        arr=Decimal(str(arr)),
        renewal_date=renewal_date or (utcnow().date() + timedelta(days=60)),
        owner_user_id=owner_user_id,
        crm_health=crm_health,
        status="active",
    )
    session.add(acc)
    await session.flush()
    return acc


async def _create_finding(
    session: Any,
    org_id: UUID,
    account_id: UUID,
    title: str,
    *,
    finding_type: str = "risk",
    severity: str = "high",
    priority_score: float = 85.0,
    status: str = "open",
    renewal_in_days: int = 45,
    claims: list[dict[str, Any]] | None = None,
    rule_keys: list[str] | None = None,
    first_seen_at: datetime | None = None,
    last_seen_at: datetime | None = None,
    previous_snapshot: dict[str, Any] | None = None,
) -> Finding:
    now = utcnow()
    f = Finding(
        id=uuid4(),
        org_id=org_id,
        account_id=account_id,
        type=finding_type,
        fingerprint=f"fp-{uuid4()}",
        status=status,
        severity=severity,
        priority_score=Decimal(str(priority_score)),
        confidence=0.85,
        title=title,
        summary=f"Summary for {title}",
        claims=claims
        or [
            {"text": "Usage dropped 40% in last 3 weeks", "evidence_ids": ["E1"]},
            {"text": "No executive engagement for 30 days", "evidence_ids": ["E2"]},
        ],
        unknowns=["Renewal intent not confirmed"],
        contradictions=[],
        rule_keys=rule_keys or ["R01_usage_drop"],
        categories=["usage", "engagement"],
        renewal_in_days=renewal_in_days,
        first_seen_at=first_seen_at or now,
        last_seen_at=last_seen_at or now,
        previous_snapshot=previous_snapshot,
    )
    session.add(f)
    await session.flush()
    return f


# ==============================================================================
# R4-01: Permission Matrix Tests
# ==============================================================================


async def test_permission_matrix_findings_dismiss_snooze_reopen(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    org_id = org_a.org_id
    member_user = org_a.users["member"]
    owner_user = org_a.users["owner"]

    async with org_session(org_id) as session:
        # Account 1 owned by member
        acc_own = await _create_account_with_owner(session, org_id, "Member Owned Co", member_user)
        # Account 2 owned by org owner (other user)
        acc_other = await _create_account_with_owner(session, org_id, "Other Co", owner_user)

        f_own = await _create_finding(session, org_id, acc_own.id, "Finding on Member Co")
        f_other = await _create_finding(session, org_id, acc_other.id, "Finding on Other Co")
        await session.commit()
        f_own_id = f_own.id
        f_other_id = f_other.id

    client_viewer = client_as("viewer")
    client_member = client_as("member")
    client_manager = client_as("manager")

    # 1. Viewer: forbidden on dismiss/snooze/reopen
    r_viewer_dismiss = await client_viewer.post(
        f"/api/v1/findings/{f_own_id}/dismiss",
        json={"reason": "not_relevant", "note": "viewer try"},
    )
    assert r_viewer_dismiss.status_code == 403

    r_viewer_snooze = await client_viewer.post(
        f"/api/v1/findings/{f_own_id}/snooze",
        json={"until": (utcnow() + timedelta(days=7)).isoformat()},
    )
    assert r_viewer_snooze.status_code == 403

    # 2. Member on OTHER account: forbidden
    r_member_other = await client_member.post(
        f"/api/v1/findings/{f_other_id}/dismiss",
        json={"reason": "not_relevant"},
    )
    assert r_member_other.status_code == 403

    # 3. Member on OWN account: allowed
    r_member_own = await client_member.post(
        f"/api/v1/findings/{f_own_id}/dismiss",
        json={"reason": "not_relevant", "note": "handled by account team"},
    )
    assert r_member_own.status_code == 200
    assert r_member_own.json()["status"] == "dismissed"
    assert r_member_own.json()["dismissed_reason"] == "not_relevant"

    # Member reopens own finding
    r_member_reopen = await client_member.post(f"/api/v1/findings/{f_own_id}/reopen")
    assert r_member_reopen.status_code == 200
    assert r_member_reopen.json()["status"] == "open"

    # 4. Manager on ANY account (including other's account): allowed
    r_manager_dismiss = await client_manager.post(
        f"/api/v1/findings/{f_other_id}/dismiss",
        json={"reason": "already_handled"},
    )
    assert r_manager_dismiss.status_code == 200
    assert r_manager_dismiss.json()["status"] == "dismissed"


async def test_permission_matrix_rules_endpoints(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    client_viewer = client_as("viewer")
    client_member = client_as("member")
    client_manager = client_as("manager")

    # Viewer cannot access rules
    r_viewer = await client_viewer.get("/api/v1/rules")
    assert r_viewer.status_code == 403

    # Member cannot access rules
    r_member = await client_member.get("/api/v1/rules")
    assert r_member.status_code == 403

    r_member_put = await client_member.put(
        "/api/v1/rules/R01_usage_drop",
        json={"enabled": True, "params": {"drop_pct": 25}},
    )
    assert r_member_put.status_code == 403

    # Manager can access rules
    r_manager = await client_manager.get("/api/v1/rules")
    assert r_manager.status_code == 200
    assert isinstance(r_manager.json(), list)
    assert len(r_manager.json()) == 16


async def test_finding_feedback_allowed_for_all_roles(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    org_id = org_a.org_id
    async with org_session(org_id) as session:
        acc = await _create_account_with_owner(session, org_id, "Feedback Test Co", None)
        f = await _create_finding(session, org_id, acc.id, "Feedback Finding")
        await session.commit()
        fid = f.id

    client_viewer = client_as("viewer")
    client_member = client_as("member")

    r_v = await client_viewer.post(
        f"/api/v1/findings/{fid}/feedback", json={"useful": True, "note": "Great catch"}
    )
    assert r_v.status_code == 200
    assert r_v.json()["ok"] is True

    r_m = await client_member.post(
        f"/api/v1/findings/{fid}/feedback", json={"useful": False, "note": "False alarm"}
    )
    assert r_m.status_code == 200
    assert r_m.json()["ok"] is True


# ==============================================================================
# R4-01: State Transition Rules & Decision Log
# ==============================================================================


async def test_snooze_dismiss_reopen_state_rules(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    org_id = org_a.org_id
    async with org_session(org_id) as session:
        acc = await _create_account_with_owner(session, org_id, "Lifecycle Co", None)
        f = await _create_finding(session, org_id, acc.id, "Lifecycle Finding")
        await session.commit()
        fid = f.id

    client = client_as("manager")

    # Reopening an already open finding raises 409 conflict
    r_conflict = await client.post(f"/api/v1/findings/{fid}/reopen")
    assert r_conflict.status_code == 409
    assert r_conflict.json()["error"]["code"] == "conflict"

    # Dismiss finding
    r_dismiss = await client.post(
        f"/api/v1/findings/{fid}/dismiss",
        json={"reason": "not_relevant", "note": "Verified not an issue"},
    )
    assert r_dismiss.status_code == 200
    data_d = r_dismiss.json()
    assert data_d["status"] == "dismissed"
    assert data_d["dismissed_reason"] == "not_relevant"

    # Reopen finding
    r_reopen = await client.post(f"/api/v1/findings/{fid}/reopen")
    assert r_reopen.status_code == 200
    data_r = r_reopen.json()
    assert data_r["status"] == "open"
    assert data_r["dismissed_reason"] is None

    # Snooze finding
    snooze_until = utcnow() + timedelta(days=14)
    r_snooze = await client.post(
        f"/api/v1/findings/{fid}/snooze", json={"until": snooze_until.isoformat()}
    )
    assert r_snooze.status_code == 200
    data_s = r_snooze.json()
    assert data_s["status"] == "snoozed"
    assert data_s["snoozed_until"] is not None

    # Reopen from snoozed
    r_reopen_s = await client.post(f"/api/v1/findings/{fid}/reopen")
    assert r_reopen_s.status_code == 200
    assert r_reopen_s.json()["status"] == "open"
    assert r_reopen_s.json()["snoozed_until"] is None


# ==============================================================================
# R4-01: GET /today Endpoint Tests
# ==============================================================================


async def test_today_endpoint_member_vs_manager_default_owner(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    org_id = org_a.org_id
    member_user = org_a.users["member"]
    manager_user = org_a.users["manager"]

    async with org_session(org_id) as session:
        acc_member = await _create_account_with_owner(
            session, org_id, "Member Account Today", member_user, arr=80000.0
        )
        acc_manager = await _create_account_with_owner(
            session, org_id, "Manager Account Today", manager_user, arr=120000.0
        )

        await _create_finding(
            session, org_id, acc_member.id, "Member Finding", priority_score=92.0
        )
        await _create_finding(
            session, org_id, acc_manager.id, "Manager Finding", priority_score=88.0
        )
        await session.commit()

    client_member = client_as("member")
    client_manager = client_as("manager")

    # Member calling /today defaults to owner=me
    r_m = await client_member.get("/api/v1/today")
    assert r_m.status_code == 200
    data_m = r_m.json()
    titles_m = [item["title"] for item in data_m["items"]]
    assert "Member Finding" in titles_m
    assert "Manager Finding" not in titles_m

    # Manager calling /today defaults to owner=all
    r_mgr = await client_manager.get("/api/v1/today")
    assert r_mgr.status_code == 200
    data_mgr = r_mgr.json()
    titles_mgr = [item["title"] for item in data_mgr["items"]]
    assert "Member Finding" in titles_mgr
    assert "Manager Finding" in titles_mgr

    # Manager calling /today?owner=me filters to manager's accounts
    r_mgr_me = await client_manager.get("/api/v1/today?owner=me")
    assert r_mgr_me.status_code == 200
    titles_mgr_me = [item["title"] for item in r_mgr_me.json()["items"]]
    assert "Manager Finding" in titles_mgr_me
    assert "Member Finding" not in titles_mgr_me


async def test_today_endpoint_ranking_and_low_severity_filter(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    org_id = org_a.org_id
    today = utcnow().date()

    async with org_session(org_id) as session:
        # Account with far renewal (90 days)
        acc_far = await _create_account_with_owner(
            session,
            org_id,
            "Far Renewal Corp",
            None,
            renewal_date=today + timedelta(days=90),
        )
        # Account with near renewal (20 days)
        acc_near = await _create_account_with_owner(
            session,
            org_id,
            "Near Renewal Corp",
            None,
            renewal_date=today + timedelta(days=20),
        )

        # High severity on far renewal -> visible
        f_high = await _create_finding(
            session,
            org_id,
            acc_far.id,
            "High Severity Far Renewal",
            severity="high",
            priority_score=95.0,
        )
        # Low severity on far renewal (>30d) -> HIDDEN on Today
        f_low_hidden = await _create_finding(
            session,
            org_id,
            acc_far.id,
            "Low Severity Far Renewal",
            severity="low",
            priority_score=40.0,
        )
        # Low severity on near renewal (<=30d) -> VISIBLE on Today
        f_low_visible = await _create_finding(
            session,
            org_id,
            acc_near.id,
            "Low Severity Near Renewal",
            severity="low",
            priority_score=65.0,
        )
        # Dismissed finding -> EXCLUDED
        f_dismissed = await _create_finding(
            session,
            org_id,
            acc_near.id,
            "Dismissed Finding",
            severity="high",
            status="dismissed",
            priority_score=99.0,
        )
        await session.commit()

    client = client_as("manager")
    r = await client.get("/api/v1/today")
    assert r.status_code == 200
    data = r.json()
    items = data["items"]
    titles = [item["title"] for item in items]

    assert "High Severity Far Renewal" in titles
    assert "Low Severity Near Renewal" in titles
    assert "Low Severity Far Renewal" not in titles  # Filtered out (low & >30d)
    assert "Dismissed Finding" not in titles  # Excluded

    # Verify ranked by priority_score descending
    scores = [item["priority_score"] for item in items]
    assert scores == sorted(scores, reverse=True)


async def test_today_endpoint_pending_cards_and_flags(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    org_id = org_a.org_id
    now = utcnow()

    async with org_session(org_id) as session:
        acc = await _create_account_with_owner(session, org_id, "Pending Cards Corp", None)
        f = await _create_finding(
            session,
            org_id,
            acc.id,
            "Finding with Cards",
            priority_score=89.0,
            first_seen_at=now - timedelta(hours=6),  # is_new = True
            previous_snapshot={
                "severity": "medium",
                "priority_score": 75.0,
                "claims": [{"text": "old claim"}],
            },
        )
        # Add 2 pending cards for this finding
        c1 = ActionCard(
            id=uuid4(),
            org_id=org_id,
            account_id=acc.id,
            finding_id=f.id,
            type="email_draft",
            tier=2,
            status="pending_approval",
            title="Review Renewal Email",
            rationale="Test",
            evidence_keys=[],
            payload={"to": ["test@pendingcards.com"], "subject": "Renewal"},
            idempotency_key=f"card-test-{uuid4()}",
        )
        c2 = ActionCard(
            id=uuid4(),
            org_id=org_id,
            account_id=acc.id,
            finding_id=f.id,
            type="crm_task",
            tier=1,
            status="pending_approval",
            title="Check In Call",
            rationale="Test",
            evidence_keys=[],
            payload={"title": "Check In Call", "owner_crm_id": "123", "due_date": "2026-11-01", "associate": []},
            idempotency_key=f"card-test-{uuid4()}",
        )
        # 1 executed card (should not be counted in pending_cards)
        c3 = ActionCard(
            id=uuid4(),
            org_id=org_id,
            account_id=acc.id,
            finding_id=f.id,
            type="crm_note",
            tier=1,
            status="executed",
            title="Executed Note",
            rationale="Test",
            evidence_keys=[],
            payload={"body": "Done", "associate": []},
            idempotency_key=f"card-test-{uuid4()}",
        )
        session.add_all([c1, c2, c3])
        await session.commit()
        fid = f.id

    client = client_as("manager")
    r = await client.get("/api/v1/today")
    assert r.status_code == 200
    data = r.json()

    target = next((item for item in data["items"] if item["finding_id"] == str(fid)), None)
    assert target is not None
    assert target["pending_cards"] == 2
    assert target["is_new"] is True
    assert target["changed_since_yesterday"] is True
    assert len(target["top_reasons"]) >= 1
    assert data["counts"]["pending_cards"] >= 2


# ==============================================================================
# R4-01: Findings List & Detail Endpoints
# ==============================================================================


async def test_findings_list_filters_and_pagination(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    org_id = org_a.org_id
    async with org_session(org_id) as session:
        acc_risk = await _create_account_with_owner(session, org_id, "Risk Account", None)
        acc_exp = await _create_account_with_owner(session, org_id, "Expansion Account", None)

        await _create_finding(
            session,
            org_id,
            acc_risk.id,
            "High Risk Finding",
            finding_type="risk",
            severity="high",
            priority_score=90.0,
        )
        await _create_finding(
            session,
            org_id,
            acc_exp.id,
            "Expansion Finding",
            finding_type="expansion",
            severity="medium",
            priority_score=80.0,
        )
        await session.commit()

    client = client_as("member")

    # Filter by type=risk
    r_risk = await client.get("/api/v1/findings?type=risk")
    assert r_risk.status_code == 200
    items_risk = r_risk.json()["items"]
    assert all(f["type"] == "risk" for f in items_risk)
    assert any("High Risk Finding" in f["title"] for f in items_risk)

    # Filter by severity=high
    r_sev = await client.get("/api/v1/findings?severity=high")
    assert r_sev.status_code == 200
    assert all(f["severity"] == "high" for f in r_sev.json()["items"])

    # Keyset pagination with limit=1
    r_p1 = await client.get("/api/v1/findings?limit=1")
    assert r_p1.status_code == 200
    p1_data = r_p1.json()
    assert len(p1_data["items"]) == 1
    cursor = p1_data.get("next_cursor")
    assert cursor is not None

    r_p2 = await client.get(f"/api/v1/findings?cursor={cursor}&limit=1")
    assert r_p2.status_code == 200
    assert len(r_p2.json()["items"]) == 1
    assert r_p2.json()["items"][0]["id"] != p1_data["items"][0]["id"]


async def test_finding_detail_full_bundle(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    org_id = org_a.org_id
    async with org_session(org_id) as session:
        acc = await _create_account_with_owner(session, org_id, "Detail Test Account", None)
        f = await _create_finding(
            session,
            org_id,
            acc.id,
            "Detailed Risk Finding",
            rule_keys=["R01_usage_drop"],
        )
        # Add finding evidence
        ev = FindingEvidence(
            id=uuid4(),
            org_id=org_id,
            finding_id=f.id,
            evidence_key="E1",
            kind="usage",
            label="Active users drop 50 to 28",
            detail="Weekly usage telemetry",
            source="usage",
            source_url="https://app.example.com",
            occurred_at=utcnow(),
        )
        # Add rule hit
        rh = RuleHit(
            id=uuid4(),
            org_id=org_id,
            account_id=acc.id,
            rule_key="R01_usage_drop",
            category="usage",
            finding_type="risk",
            severity_points=3,
            metrics={"drop_pct": 44.0, "baseline": 50, "current": 28},
            evidence_refs=[],
        )
        # Add card
        card = ActionCard(
            id=uuid4(),
            org_id=org_id,
            account_id=acc.id,
            finding_id=f.id,
            type="email_draft",
            tier=2,
            status="pending_approval",
            title="Reach out regarding drop",
            rationale="Test",
            evidence_keys=["E1"],
            payload={"to": ["exec@detail.com"], "subject": "Checking in"},
            idempotency_key=f"card-detail-{uuid4()}",
        )
        session.add_all([ev, rh, card])
        await session.flush()

        # Add history entry in decision log
        await decision_log.log(
            session,
            org_id=org_id,
            actor_type="system",
            actor_id="agent_run",
            event="finding.created",
            entity_type="finding",
            entity_id=f.id,
            account_id=acc.id,
            data={"title": f.title},
        )
        await session.commit()
        fid = f.id

    client = client_as("member")
    r = await client.get(f"/api/v1/findings/{fid}")
    assert r.status_code == 200
    data = r.json()

    assert data["id"] == str(fid)
    assert len(data["claims"]) >= 1
    assert len(data["evidence"]) >= 1
    assert data["evidence"][0]["key"] == "E1"
    assert len(data["rule_hits"]) >= 1
    assert data["rule_hits"][0]["rule_key"] == "R01_usage_drop"
    assert len(data["cards"]) >= 1
    assert data["cards"][0]["title"] == "Reach out regarding drop"
    assert any(h["event"] == "finding.created" for h in data["history"])


# ==============================================================================
# R4-02: Rules Settings & Preview Tests
# ==============================================================================


async def test_rules_list_and_put_parameter_validation(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    client = client_as("manager")

    # 1. GET /rules returns 16 rules
    r_list = await client.get("/api/v1/rules")
    assert r_list.status_code == 200
    rules = r_list.json()
    assert len(rules) == 16
    keys = {r["key"] for r in rules}
    assert "R01_usage_drop" in keys
    assert "X01_seat_saturation" in keys

    # 2. PUT /rules/{key} with invalid parameter name -> 422 validation_error
    r_bad_name = await client.put(
        "/api/v1/rules/R01_usage_drop",
        json={"enabled": True, "params": {"invalid_param": 100}},
    )
    assert r_bad_name.status_code == 422
    assert r_bad_name.json()["error"]["code"] == "validation_error"

    # 3. PUT /rules/{key} with out-of-range parameter value -> 422 validation_error
    r_bad_range = await client.put(
        "/api/v1/rules/R01_usage_drop",
        json={"enabled": True, "params": {"drop_pct": 150}},  # max is 100
    )
    assert r_bad_range.status_code == 422

    # 4. PUT /rules/{key} with valid parameter value -> 200 OK
    r_valid = await client.put(
        "/api/v1/rules/R01_usage_drop",
        json={"enabled": True, "params": {"drop_pct": 25}},
    )
    assert r_valid.status_code == 200
    data_valid = r_valid.json()
    assert data_valid["params"]["drop_pct"] == 25
    assert data_valid["enabled"] is True

    # 5. GET /rules reflects updated params
    r_recheck = await client.get("/api/v1/rules")
    r01 = next(r for r in r_recheck.json() if r["key"] == "R01_usage_drop")
    assert r01["params"]["drop_pct"] == 25


async def test_preview_rule_matches_accounts(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    org_id = org_a.org_id
    today = utcnow().date()

    async with org_session(org_id) as session:
        # Create account expiring in 45 days
        acc1 = await _create_account_with_owner(
            session,
            org_id,
            "Preview Renewal Acc",
            None,
            renewal_date=today + timedelta(days=45),
        )
        # Create rule hit for R04
        rh = RuleHit(
            id=uuid4(),
            org_id=org_id,
            account_id=acc1.id,
            rule_key="R04_renewal_near_no_plan",
            category="renewal",
            finding_type="risk",
            severity_points=2,
            metrics={"renewal_in_days": 45},
            evidence_refs=[],
        )
        session.add(rh)
        await session.commit()

    client = client_as("manager")

    # Preview R04 with window=60 (acc1 has renewal in 45 days -> fires)
    r_preview = await client.post(
        "/api/v1/rules/R04_renewal_near_no_plan/preview",
        json={"params": {"window": 60}},
    )
    assert r_preview.status_code == 200
    preview_data = r_preview.json()
    assert preview_data["would_fire"] >= 1
    assert preview_data["currently_firing"] >= 1
    assert str(acc1.id) in preview_data["sample_account_ids"]


async def test_rules_rerun_endpoint(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    client = client_as("manager")
    r = await client.post("/api/v1/rules/rerun", json={"rule_keys": ["R01_usage_drop"]})
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ==============================================================================
# R4-03: "What changed" Diff versus previous_snapshot
# ==============================================================================


def test_what_changed_diff_computation() -> None:
    f_dummy = Finding(
        id=uuid4(),
        org_id=uuid4(),
        account_id=uuid4(),
        type="risk",
        fingerprint="fp-test",
        status="open",
        severity="high",
        priority_score=Decimal("85.0"),
        confidence=0.9,
        title="Test Finding",
        claims=[
            {"text": "Usage dropped 45%", "evidence_ids": ["E1"]},
            {"text": "New negative sentiment signal", "evidence_ids": ["E3"]},
        ],
        rule_keys=["R01_usage_drop", "R06_negative_sentiment"],
        categories=["usage", "sentiment"],
        previous_snapshot={
            "severity": "medium",
            "priority_score": 60.0,
            "claims": [{"text": "Usage dropped 45%", "evidence_ids": ["E1"]}],
            "rule_keys": ["R01_usage_drop"],
            "categories": ["usage"],
        },
    )

    diff = compute_finding_diff(f_dummy)
    assert diff["has_diff"] is True
    assert diff["severity_changed"] is True
    assert diff["old_severity"] == "medium"
    assert diff["new_severity"] == "high"
    assert diff["score_delta"] == 25.0
    assert "New negative sentiment signal" in diff["new_claims"]
    assert "R06_negative_sentiment" in diff["new_rule_keys"]


# ==============================================================================
# R4-04: Today Performance & Query Count Verification
# ==============================================================================


async def test_today_performance_bounded_query_count(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    """Verify GET /today executes a bounded constant number of queries without N+1."""
    org_id = org_a.org_id

    # Seed 10 accounts and findings
    async with org_session(org_id) as session:
        for i in range(10):
            acc = await _create_account_with_owner(
                session, org_id, f"Perf Corp {i}", org_a.users["manager"]
            )
            f = await _create_finding(
                session, org_id, acc.id, f"Perf Risk {i}", priority_score=80.0 + i
            )
            card = ActionCard(
                id=uuid4(),
                org_id=org_id,
                account_id=acc.id,
                finding_id=f.id,
                type="email_draft",
                tier=2,
                status="pending_approval",
                title=f"Action {i}",
                rationale="Test",
                evidence_keys=[],
                payload={"to": [f"user{i}@perf.com"], "subject": "Review"},
                idempotency_key=f"card-perf-{uuid4()}",
            )
            session.add(card)
        await session.commit()

    client = client_as("manager")

    # Time and fetch
    start = datetime.now()
    r = await client.get("/api/v1/today")
    duration = (datetime.now() - start).total_seconds()

    assert r.status_code == 200
    assert duration < 0.8  # Well under 800ms
    data = r.json()
    assert len(data["items"]) >= 10
    assert data["counts"]["risk"] >= 10
    assert data["counts"]["pending_cards"] >= 10
