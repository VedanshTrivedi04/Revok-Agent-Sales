"""Mock handlers for /analytics/* (MOCK_API=true): the same aggregates, computed over the in-memory
fixture store instead of SQL, so they move when a mock card is approved or a finding dismissed."""

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import Request

from app.mocks.handlers import mock, store
from app.models.brain import CATEGORIES
from app.services.analytics import (
    APPROVED_STATES,
    OPEN_FINDINGS,
    RISK_LEVELS,
    SEVERITY_RANK,
    _month_start,
    _ratio,
    _weeks,
    resolve_window,
)
from app.utils.time import utcnow


def _day(ts: str | None) -> date | None:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).date() if ts else None


def _monday(ts: str | None) -> date | None:
    d = _day(ts)
    return d - timedelta(days=d.weekday()) if d else None


def _slices(counter: Counter[Any]) -> list[dict[str, Any]]:
    return [{"key": str(k), "count": n} for k, n in counter.most_common() if k is not None]


def _scope(owner_id: Any) -> tuple[list[Any], list[Any], list[Any]]:
    """(accounts, findings, cards), narrowed to one owner's accounts when asked."""
    s = store().d
    accounts = [a for a in s["accounts"]["list"] if a["status"] == "active"]
    if owner_id is not None:
        accounts = [a for a in accounts if (a.get("owner") or {}).get("id") == str(owner_id)]
    ids = {a["id"] for a in accounts}
    return (
        accounts,
        [f for f in s["findings"] if f["account_id"] in ids],
        [c for c in s["cards"] if c["account_id"] in ids],
    )


def _approved(c: dict[str, Any]) -> bool:
    return c["status"] in APPROVED_STATES


def _edited(c: dict[str, Any]) -> bool:
    return _approved(c) and c.get("edited_payload") is not None


def _decisions_trend(cards: list[Any], w: Any) -> list[dict[str, Any]]:
    return [
        {
            "week": wk,
            "approved": sum(1 for c in cards if _approved(c) and _monday(c["decided_at"]) == wk),
            "rejected": sum(
                1 for c in cards if c["status"] == "rejected" and _monday(c["decided_at"]) == wk
            ),
            "edited": sum(1 for c in cards if _edited(c) and _monday(c["decided_at"]) == wk),
        }
        for wk in _weeks(w)
    ]


def _at_risk(findings: list[Any]) -> set[str]:
    return {
        f["account_id"]
        for f in findings
        if f["type"] == "risk"
        and f["status"] in OPEN_FINDINGS
        and f["severity"] in ("high", "medium")
    }


@mock("analytics_overview")
def m_overview(
    request: Request, from_: Any = None, to: Any = None, owner_id: Any = None, **_: Any
) -> Any:
    w = resolve_window(from_, to)
    accounts, findings, cards = _scope(owner_id)
    risky = _at_risk(findings)
    open_f = [f for f in findings if f["status"] in OPEN_FINDINGS]
    due = [a for a in accounts if 0 <= (a.get("renewal_in_days") or -1) <= 90]
    levels = Counter(a.get("risk_level") or "none" for a in accounts)
    return {
        "window": w,
        "currency": store().d["org"]["currency"],
        "kpis": {
            "accounts_total": len(accounts),
            "accounts_at_risk": sum(1 for a in accounts if a["id"] in risky),
            "arr_total": sum(a.get("arr") or 0 for a in accounts),
            "arr_at_risk": sum(a.get("arr") or 0 for a in accounts if a["id"] in risky),
            "open_findings": len(open_f),
            "open_high_findings": sum(1 for f in open_f if f["severity"] == "high"),
            "pending_approvals": sum(1 for c in cards if c["status"] == "pending_approval"),
            "expansion_value": sum(
                f.get("value_at_stake") or 0 for f in open_f if f["type"] == "expansion"
            ),
            "renewals_due_90d": len(due),
            "renewals_due_90d_arr": sum(a.get("arr") or 0 for a in due),
        },
        "findings_trend": [
            {
                "week": wk,
                "risk": sum(
                    1 for f in findings if f["type"] == "risk" and _monday(f["first_seen_at"]) == wk
                ),
                "expansion": sum(
                    1
                    for f in findings
                    if f["type"] == "expansion" and _monday(f["first_seen_at"]) == wk
                ),
            }
            for wk in _weeks(w)
        ],
        "decisions_trend": _decisions_trend(cards, w),
        "risk_levels": [{"key": k, "count": levels.get(k, 0)} for k in RISK_LEVELS],
    }


@mock("analytics_pipeline")
def m_pipeline(
    request: Request, from_: Any = None, to: Any = None, owner_id: Any = None, **_: Any
) -> Any:
    w = resolve_window(from_, to)
    accounts, findings, _cards = _scope(owner_id)
    by_account = store().d["accounts"]["deals"]
    deals = [d for a in accounts for d in by_account.get(a["id"], [])]
    open_deals = [d for d in deals if not d["is_closed"]]
    closed = [
        d for d in deals if d["is_closed"] and w.start <= (_day(d["close_date"]) or w.end) <= w.end
    ]
    won = [d for d in closed if d["is_won"]]
    lost = [d for d in closed if not d["is_won"]]

    def amount(rows: list[Any]) -> float:
        return float(sum(d.get("amount") or 0 for d in rows))

    stages: dict[str, list[Any]] = {}
    for d in open_deals:
        stages.setdefault(d.get("stage_label") or "unknown", []).append(d)
    types = sorted({d.get("deal_type") or "other" for d in deals})
    risky = _at_risk(findings)
    today = utcnow().date()
    months = [_month_start(today, i) for i in range(12)]

    def renewing(m: date) -> list[Any]:
        return [
            a for a in accounts if a.get("renewal_date") and _month_start(_day(a["renewal_date"])) == m
        ]  # fmt: skip

    return {
        "window": w,
        "currency": store().d["org"]["currency"],
        "totals": {
            "open_count": len(open_deals),
            "open_amount": amount(open_deals),
            "won_count": len(won),
            "won_amount": amount(won),
            "lost_count": len(lost),
            "lost_amount": amount(lost),
            "win_rate": _ratio(len(won), len(won) + len(lost)),
        },
        "stages": [
            {"stage": k, "label": k, "open_count": len(v), "open_amount": amount(v)}
            for k, v in sorted(stages.items(), key=lambda kv: -amount(kv[1]))
        ],
        "deal_types": [
            {
                "deal_type": t,
                "open_count": sum(1 for d in open_deals if (d.get("deal_type") or "other") == t),
                "open_amount": amount(
                    [d for d in open_deals if (d.get("deal_type") or "other") == t]
                ),
                "won_count": sum(1 for d in won if (d.get("deal_type") or "other") == t),
                "won_amount": amount([d for d in won if (d.get("deal_type") or "other") == t]),
                "lost_count": sum(1 for d in lost if (d.get("deal_type") or "other") == t),
            }
            for t in types
        ],
        "renewals": [
            {
                "month": m,
                "count": len(renewing(m)),
                "arr": float(sum(a.get("arr") or 0 for a in renewing(m))),
                "at_risk_arr": float(
                    sum(a.get("arr") or 0 for a in renewing(m) if a["id"] in risky)
                ),
            }
            for m in months
        ],
    }


@mock("analytics_risk")
def m_risk(request: Request, owner_id: Any = None, **_: Any) -> Any:
    accounts, findings, _cards = _scope(owner_id)
    open_f = [f for f in findings if f["status"] in OPEN_FINDINGS]
    count = Counter(f["account_id"] for f in open_f)
    scored = sorted(
        (a for a in accounts if a.get("priority_score") is not None),
        key=lambda a: -a["priority_score"],
    )

    def cells(account_id: str) -> list[dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for f in open_f:
            if f["account_id"] != account_id:
                continue
            for cat in {h["category"] for h in f.get("rule_hits", [])}:
                cell = out.setdefault(
                    cat, {"category": cat, "findings": 0, "top_severity": f["severity"]}
                )
                cell["findings"] += 1
                if SEVERITY_RANK[f["severity"]] > SEVERITY_RANK[cell["top_severity"]]:
                    cell["top_severity"] = f["severity"]
        return [out[c] for c in CATEGORIES if c in out]

    return {
        "currency": store().d["org"]["currency"],
        "categories": list(CATEGORIES),
        "heatmap": [
            {
                "account_id": a["id"],
                "account_name": a["name"],
                "arr": a.get("arr"),
                "priority_score": a["priority_score"],
                "cells": cells(a["id"]),
            }
            for a in scored
            if count.get(a["id"])
        ][:15],
        "bubbles": [
            {
                "account_id": a["id"],
                "account_name": a["name"],
                "arr": a.get("arr"),
                "priority_score": a["priority_score"],
                "risk_level": a.get("risk_level"),
                "renewal_in_days": a.get("renewal_in_days"),
                "open_findings": count.get(a["id"], 0),
            }
            for a in scored
        ],
        "risk_levels": [
            {
                "key": k,
                "count": sum(1 for a in accounts if (a.get("risk_level") or "none") == k),
                "arr": float(
                    sum(a.get("arr") or 0 for a in accounts if (a.get("risk_level") or "none") == k)
                ),
            }
            for k in RISK_LEVELS
        ],
    }


@mock("analytics_findings")
def m_findings(
    request: Request, from_: Any = None, to: Any = None, owner_id: Any = None, **_: Any
) -> Any:
    w = resolve_window(from_, to)
    _accounts, findings, _cards = _scope(owner_id)
    rows = [f for f in findings if w.start <= (_day(f["first_seen_at"]) or w.start) <= w.end]
    hits = [h for f in rows for h in f.get("rule_hits", [])]
    return {
        "window": w,
        "total": len(rows),
        "trend": [
            {
                "week": wk,
                **{
                    sev: sum(
                        1
                        for f in rows
                        if f["severity"] == sev and _monday(f["first_seen_at"]) == wk
                    )
                    for sev in ("high", "medium", "low")
                },
            }
            for wk in _weeks(w)
        ],
        "by_rule": _slices(Counter(h["rule_key"] for h in hits)),
        "by_category": _slices(Counter(h["category"] for h in hits)),
        "by_status": _slices(Counter(f["status"] for f in rows)),
        "by_type": _slices(Counter(f["type"] for f in rows)),
        "dismissed_reasons": _slices(Counter(f.get("dismissed_reason") for f in rows)),
    }


@mock("analytics_team")
def m_team(request: Request, from_: Any = None, to: Any = None, **_: Any) -> Any:
    w = resolve_window(from_, to)
    accounts, findings, cards = _scope(None)
    open_f = [f for f in findings if f["status"] in OPEN_FINDINGS]
    owner_of = {a["id"]: (a.get("owner") or {}).get("id") for a in accounts}

    def row(m: dict[str, Any]) -> dict[str, Any]:
        uid = m["user_id"]
        mine = [a for a in accounts if owner_of[a["id"]] == uid]
        decided = [c for c in cards if c.get("decided_by") == uid]
        return {
            "user_id": uid,
            "name": m["name"] or m["email"],
            "role": m["role"],
            "accounts_owned": len(mine),
            "arr_owned": float(sum(a.get("arr") or 0 for a in mine)),
            "open_findings": sum(1 for f in open_f if owner_of.get(f["account_id"]) == uid),
            "pending_cards": sum(
                1
                for c in cards
                if c["status"] == "pending_approval" and c.get("assignee_user_id") == uid
            ),
            "approved": sum(1 for c in decided if _approved(c)),
            "rejected": sum(1 for c in decided if c["status"] == "rejected"),
            "median_decision_hours": None,
        }

    nobody = [a for a in accounts if owner_of[a["id"]] is None]
    return {
        "window": w,
        "currency": store().d["org"]["currency"],
        "members": [row(m) for m in store().d["members"]["members"] if m["status"] == "active"],
        "unassigned": {
            "accounts": len(nobody),
            "arr": float(sum(a.get("arr") or 0 for a in nobody)),
        },
    }


@mock("analytics_automation")
def m_automation(
    request: Request, from_: Any = None, to: Any = None, owner_id: Any = None, **_: Any
) -> Any:
    w = resolve_window(from_, to)
    _accounts, _findings, cards = _scope(owner_id)
    approved = [c for c in cards if _approved(c)]
    rejected = [c for c in cards if c["status"] == "rejected"]
    edited = [c for c in cards if _edited(c)]

    def of(rows: list[Any], key: str, value: Any) -> int:
        return sum(1 for c in rows if c[key] == value)

    return {
        "window": w,
        "totals": {
            "proposed": len(cards),
            "approved": len(approved),
            "rejected": len(rejected),
            "edited": len(edited),
            "executed": sum(1 for c in cards if c["status"] in ("executed", "reverted")),
            "failed": of(cards, "status", "failed"),
            "reverted": of(cards, "status", "reverted"),
            "expired": of(cards, "status", "expired"),
            "approval_rate": _ratio(len(approved), len(approved) + len(rejected)),
            "edit_rate": _ratio(len(edited), len(approved)),
            "median_decision_hours": None,
        },
        "by_type": [
            {
                "type": t,
                "total": of(cards, "type", t),
                "approved": of(approved, "type", t),
                "rejected": of(rejected, "type", t),
                "edited": of(edited, "type", t),
                "failed": sum(1 for c in cards if c["type"] == t and c["status"] == "failed"),
                "reverted": sum(1 for c in cards if c["type"] == t and c["status"] == "reverted"),
            }
            for t in sorted({c["type"] for c in cards})
        ],
        "by_tier": [
            {
                "tier": t,
                "total": of(cards, "tier", t),
                "approved": of(approved, "tier", t),
                "rejected": of(rejected, "tier", t),
            }
            for t in sorted({c["tier"] for c in cards})
        ],
        "channels": _slices(Counter(c.get("decision_channel") for c in cards)),
        "rejection_reasons": _slices(Counter(c.get("rejection_reason") for c in cards)),
        "trend": _decisions_trend(cards, w),
    }


@mock("analytics_data_health")
def m_analytics_data_health(request: Request, from_: Any = None, to: Any = None, **_: Any) -> Any:
    w = resolve_window(from_, to)
    s = store().d
    accounts, _findings, _cards = _scope(None)
    groups: dict[tuple[str, str], list[Any]] = {}
    for i in s["integrations"]["integrations"]:
        groups.setdefault((i["provider"], i["status"]), []).append(i)
    days = Counter(
        (_day(r["started_at"]), r["status"])
        for r in s["integrations"]["sync_runs"]
        if w.start <= (_day(r["started_at"]) or w.start) <= w.end
    )
    total = len(accounts)

    def covered(key: str, n: int) -> dict[str, Any]:
        return {"key": key, "covered": n, "total": total}

    return {
        "window": w,
        "integrations": [
            {
                "provider": provider,
                "status": status,
                "count": len(rows),
                "last_success_at": max(
                    (r["last_success_at"] for r in rows if r.get("last_success_at")), default=None
                ),
                "errors": sum(1 for r in rows if r.get("last_error")),
            }
            for (provider, status), rows in sorted(groups.items())
        ],
        "sync_trend": [
            {
                "day": d,
                "success": days.get((d, "success"), 0),
                "partial": days.get((d, "partial"), 0),
                "failed": days.get((d, "failed"), 0),
            }
            for d in sorted({k[0] for k in days if k[0]})
        ],
        "coverage": [
            covered("arr", sum(1 for a in accounts if a.get("arr") is not None)),
            covered("renewal_date", sum(1 for a in accounts if a.get("renewal_date"))),
            covered("owner", sum(1 for a in accounts if a.get("owner"))),
            covered("contacts", sum(1 for a in accounts if s["accounts"]["contacts"].get(a["id"]))),
            covered("usage_30d", sum(1 for a in accounts if s["accounts"]["usage"].get(a["id"]))),
            covered("activity_30d", sum(1 for a in accounts if a.get("last_activity_at"))),
        ],
        "matching": {
            "events": sum(len(v) for v in s["accounts"]["timeline"].values()),
            "unmatched": 0,
            "open_reviews": sum(1 for r in s["ops"]["entity_reviews"] if r.get("status") == "open"),
        },
        "runs": _slices(Counter(r["status"] for r in s["ops"]["runs"])),
    }
