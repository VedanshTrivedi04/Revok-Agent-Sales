"""Control-portal analytics: aggregates are correct, tenant-scoped, admin-only and honest when the
organization has no data yet."""

from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient

from app.contract import V1
from app.utils.time import utcnow
from tests.factories import AccountFactory, CardFactory, DealFactory, FindingFactory, persist
from tests.helpers import SeededOrg

ENDPOINTS = ["overview", "pipeline", "risk", "findings", "team", "automation", "data-health"]
ClientAs = Callable[..., AsyncClient]


async def _seed(org: SeededOrg) -> dict[str, Any]:
    """Three accounts: A (member's, at risk, renews soon), B (manager's, healthy), C (nobody's)."""
    o, now = org.org_id, utcnow()
    today = now.date()
    a = AccountFactory.build(
        org_id=o,
        name="Alpha",
        owner_user_id=org.users["member"],
        arr=Decimal("100000"),
        renewal_date=today + timedelta(days=30),
        risk_level="high",
        priority_score=Decimal("90"),
    )
    b = AccountFactory.build(
        org_id=o,
        name="Beta",
        owner_user_id=org.users["manager"],
        arr=Decimal("40000"),
        renewal_date=today + timedelta(days=200),
        risk_level="low",
        priority_score=Decimal("20"),
    )
    c = AccountFactory.build(
        org_id=o, name="Gamma", arr=None, renewal_date=None, priority_score=Decimal("95")
    )
    f_risk = FindingFactory.build(
        org_id=o,
        account_id=a.id,
        severity="high",
        rule_keys=["R01_usage_drop", "R02_no_contact"],
        categories=["usage", "engagement"],
    )
    f_exp = FindingFactory.build(
        org_id=o,
        account_id=a.id,
        type="expansion",
        severity="medium",
        value_at_stake=Decimal("5000"),
        rule_keys=["X01_seat_growth"],
        categories=["expansion"],
    )
    # an open finding with no category: counted everywhere, but it has no cell in the heatmap
    f_bare = FindingFactory.build(
        org_id=o, account_id=c.id, severity="low", rule_keys=[], categories=[]
    )
    f_done = FindingFactory.build(
        org_id=o,
        account_id=b.id,
        severity="low",
        status="dismissed",
        dismissed_reason="not_relevant",
    )
    approved = CardFactory.build(
        org_id=o,
        account_id=a.id,
        finding_id=f_risk.id,
        status="executed",
        edited_payload={"subject": "edited"},
        decided_by=org.users["member"],
        decided_at=now,
        created_at=now - timedelta(hours=2),
        decision_channel="web",
    )
    rejected = CardFactory.build(
        org_id=o,
        account_id=a.id,
        type="email_draft",
        tier=2,
        status="rejected",
        decided_by=org.users["manager"],
        decided_at=now,
        created_at=now - timedelta(hours=4),
        decision_channel="slack",
        rejection_reason="wrong_action",
    )
    pending = CardFactory.build(org_id=o, account_id=b.id, assignee_user_id=org.users["manager"])
    deals = [
        DealFactory.build(org_id=o, account_id=a.id, stage="negotiation", stage_label="Negotiation",
                          amount=Decimal("100000")),
        DealFactory.build(org_id=o, account_id=b.id, is_closed=True, is_won=True,
                          close_date=today, amount=Decimal("40000")),
        DealFactory.build(org_id=o, account_id=b.id, is_closed=True, is_won=False,
                          close_date=today, amount=Decimal("10000")),
    ]  # fmt: skip
    await persist(o, a, b, c, f_risk, f_exp, f_bare, f_done, approved, rejected, pending, *deals)
    return {"a": a, "b": b, "c": c}


async def _get(client: AsyncClient, name: str, **params: Any) -> Any:
    r = await client.get(f"{V1}/analytics/{name}", params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def test_overview_kpis_and_trends(client_as: ClientAs, org_a: SeededOrg) -> None:
    await _seed(org_a)
    data = await _get(client_as("owner"), "overview")
    k = data["kpis"]
    assert (k["accounts_total"], k["accounts_at_risk"]) == (3, 1)
    assert (k["arr_total"], k["arr_at_risk"]) == (140000, 100000)
    assert (k["open_findings"], k["open_high_findings"], k["pending_approvals"]) == (3, 1, 1)
    assert k["expansion_value"] == 5000
    assert (k["renewals_due_90d"], k["renewals_due_90d_arr"]) == (1, 100000)
    assert {s["key"]: s["count"] for s in data["risk_levels"]} == {
        "high": 1, "medium": 0, "low": 1, "none": 1,
    }  # fmt: skip
    # dense weekly series: every week of the window is present, the totals land in the last one
    assert len(data["findings_trend"]) >= 13
    assert sum(w["risk"] for w in data["findings_trend"]) == 3
    assert sum(w["expansion"] for w in data["findings_trend"]) == 1
    decisions = data["decisions_trend"]
    assert [sum(w[key] for w in decisions) for key in ("approved", "rejected", "edited")] == [
        1, 1, 1,
    ]  # fmt: skip


async def test_owner_filter_narrows_to_that_persons_accounts(
    client_as: ClientAs, org_a: SeededOrg
) -> None:
    await _seed(org_a)
    data = await _get(client_as("admin"), "overview", owner_id=str(org_a.users["manager"]))
    k = data["kpis"]
    assert (k["accounts_total"], k["arr_total"], k["open_findings"]) == (1, 40000, 0)
    assert (k["pending_approvals"], k["accounts_at_risk"]) == (1, 0)


async def test_pipeline_totals_stages_and_renewals(client_as: ClientAs, org_a: SeededOrg) -> None:
    await _seed(org_a)
    data = await _get(client_as("owner"), "pipeline")
    t = data["totals"]
    assert (t["open_count"], t["open_amount"]) == (1, 100000)
    assert (t["won_count"], t["won_amount"], t["lost_count"], t["lost_amount"]) == (
        1, 40000, 1, 10000,
    )  # fmt: skip
    assert t["win_rate"] == 0.5
    assert data["stages"] == [
        {"stage": "negotiation", "label": "Negotiation", "open_count": 1, "open_amount": 100000}
    ]
    assert len(data["renewals"]) == 12
    assert sum(m["count"] for m in data["renewals"]) == 2
    assert sum(m["at_risk_arr"] for m in data["renewals"]) == 100000


async def test_risk_heatmap_and_bubbles(client_as: ClientAs, org_a: SeededOrg) -> None:
    ids = await _seed(org_a)
    data = await _get(client_as("owner"), "risk")
    assert [r["account_name"] for r in data["heatmap"]] == [
        "Alpha"
    ]  # Gamma ranks higher but its only open finding has no category
    cells = {c["category"]: c for c in data["heatmap"][0]["cells"]}
    assert set(cells) == {"usage", "engagement", "expansion"}
    assert cells["usage"] == {"category": "usage", "findings": 1, "top_severity": "high"}
    assert [b["account_name"] for b in data["bubbles"]] == ["Gamma", "Alpha", "Beta"]  # by priority
    alpha = data["bubbles"][1]
    assert alpha["account_id"] == str(ids["a"].id)
    assert (alpha["open_findings"], alpha["renewal_in_days"], alpha["risk_level"]) == (
        2,
        30,
        "high",
    )
    assert {r["key"]: r["arr"] for r in data["risk_levels"]}["high"] == 100000


async def test_findings_breakdowns(client_as: ClientAs, org_a: SeededOrg) -> None:
    await _seed(org_a)
    data = await _get(client_as("owner"), "findings")
    assert data["total"] == 4
    by = lambda name: {s["key"]: s["count"] for s in data[name]}  # noqa: E731
    assert by("by_rule") == {"R01_usage_drop": 2, "R02_no_contact": 1, "X01_seat_growth": 1}
    assert by("by_category") == {"usage": 2, "engagement": 1, "expansion": 1}
    assert by("by_status") == {"open": 3, "dismissed": 1}
    assert by("by_type") == {"risk": 3, "expansion": 1}
    assert by("dismissed_reasons") == {"not_relevant": 1}
    assert [sum(w[s] for w in data["trend"]) for s in ("high", "medium", "low")] == [1, 1, 2]


async def test_team_rows_and_unassigned(client_as: ClientAs, org_a: SeededOrg) -> None:
    await _seed(org_a)
    data = await _get(client_as("owner"), "team")
    rows = {m["user_id"]: m for m in data["members"]}
    assert len(rows) == 5  # one per seeded role
    member, manager = rows[str(org_a.users["member"])], rows[str(org_a.users["manager"])]
    assert (member["accounts_owned"], member["arr_owned"], member["open_findings"]) == (
        1,
        100000,
        2,
    )
    assert (member["approved"], member["rejected"]) == (1, 0)
    assert member["median_decision_hours"] == pytest.approx(2, abs=0.05)
    assert (manager["pending_cards"], manager["rejected"], manager["approved"]) == (1, 1, 0)
    assert data["unassigned"] == {"accounts": 1, "arr": 0}


async def test_automation_rates(client_as: ClientAs, org_a: SeededOrg) -> None:
    await _seed(org_a)
    data = await _get(client_as("owner"), "automation")
    t = data["totals"]
    assert (t["proposed"], t["approved"], t["rejected"], t["edited"], t["executed"]) == (
        3, 1, 1, 1, 1,
    )  # fmt: skip
    assert (t["approval_rate"], t["edit_rate"]) == (0.5, 1.0)
    assert t["median_decision_hours"] == pytest.approx(3, abs=0.05)
    assert {r["type"]: r["total"] for r in data["by_type"]} == {"email_draft": 1, "crm_task": 2}
    assert {r["tier"]: r["total"] for r in data["by_tier"]} == {1: 2, 2: 1}
    assert {s["key"]: s["count"] for s in data["channels"]} == {"web": 1, "slack": 1}
    assert data["rejection_reasons"] == [{"key": "wrong_action", "count": 1}]


async def test_data_health_coverage(client_as: ClientAs, org_a: SeededOrg) -> None:
    await _seed(org_a)
    data = await _get(client_as("owner"), "data-health")
    cov = {c["key"]: (c["covered"], c["total"]) for c in data["coverage"]}
    assert cov["arr"] == (2, 3) and cov["renewal_date"] == (2, 3) and cov["owner"] == (2, 3)
    assert cov["contacts"] == (0, 3) and cov["usage_30d"] == (0, 3)
    assert data["matching"] == {"events": 0, "unmatched": 0, "open_reviews": 0}
    assert data["integrations"] == [] and data["sync_trend"] == [] and data["runs"] == []


@pytest.mark.parametrize("name", ENDPOINTS)
async def test_empty_org_returns_zeros_not_errors(
    client_as: ClientAs, org_a: SeededOrg, name: str
) -> None:
    data = await _get(client_as("owner"), name)
    if name == "overview":
        assert data["kpis"]["accounts_total"] == 0 and data["kpis"]["arr_total"] == 0
    if name == "pipeline":
        assert data["totals"]["win_rate"] is None and data["stages"] == []
    if name == "risk":
        assert data["heatmap"] == [] and data["bubbles"] == []
    if name == "automation":
        assert data["totals"]["approval_rate"] is None and data["by_type"] == []


@pytest.mark.parametrize("name", ENDPOINTS)
async def test_other_tenants_data_is_invisible(
    client_as: ClientAs, org_a: SeededOrg, org_b: SeededOrg, name: str
) -> None:
    await _seed(org_b)
    data = await _get(client_as("owner"), name)
    if name == "overview":
        assert data["kpis"]["accounts_total"] == 0 and data["kpis"]["open_findings"] == 0
    if name == "pipeline":
        assert data["totals"]["open_count"] == 0
    if name == "risk":
        assert data["bubbles"] == []
    if name == "findings":
        assert data["total"] == 0
    if name == "team":
        assert all(m["accounts_owned"] == 0 for m in data["members"])
        assert {m["user_id"] for m in data["members"]} == {str(u) for u in org_a.users.values()}
    if name == "automation":
        assert data["totals"]["proposed"] == 0
    if name == "data-health":
        assert data["coverage"][0]["total"] == 0


@pytest.mark.parametrize("role", ["manager", "member", "viewer"])
async def test_analytics_is_admin_only(client_as: ClientAs, role: str) -> None:
    r = await client_as(role).get(f"{V1}/analytics/overview")
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"


async def test_window_is_validated_and_echoed(client_as: ClientAs) -> None:
    c = client_as("owner")
    ok = await c.get(f"{V1}/analytics/findings", params={"from": "2026-01-01", "to": "2026-01-31"})
    assert ok.status_code == 200
    assert ok.json()["window"] == {"start": "2026-01-01", "end": "2026-01-31"}
    assert len(ok.json()["trend"]) == 5  # Mondays 29 Dec .. 26 Jan
    backwards = await c.get(
        f"{V1}/analytics/findings", params={"from": "2026-02-01", "to": "2026-01-01"}
    )
    assert backwards.status_code == 422
    too_long = await c.get(
        f"{V1}/analytics/findings", params={"from": "2024-01-01", "to": "2026-01-01"}
    )
    assert too_long.status_code == 422
