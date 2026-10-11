"""Mock handlers for /assistant/* (MOCK_API=true): the real planner and answer text, with the facts
computed over the in-memory fixture store instead of SQL."""

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import Request

from app.mocks.analytics import _approved, _at_risk, _edited
from app.mocks.handlers import mock, store
from app.services import assistant as svc
from app.services.analytics import OPEN_FINDINGS
from app.utils.time import utcnow


def _ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value[:10]) if value else None


def _after(value: str | None, since: datetime) -> bool:
    ts = _ts(value)
    return ts is not None and ts >= since


def _facts(plan: svc.Plan, now: datetime) -> svc.Facts:
    s, p = store().d, plan.params
    accounts = [a for a in s["accounts"]["list"] if a["status"] == "active"]
    findings, cards = s["findings"], s["cards"]
    limit = p.get("limit", 10)
    since = now - timedelta(days=p.get("days", 0))
    open_risk = [f for f in findings if f["type"] == "risk" and f["status"] in OPEN_FINDINGS]

    if plan.question_id == "high_risk_accounts":
        best: dict[str, float] = {}
        for f in open_risk:
            if f["priority_score"] >= p["min_score"]:
                best[f["account_id"]] = max(best.get(f["account_id"], 0), f["priority_score"])
        hit = sorted(
            (a for a in accounts if a["id"] in best), key=lambda a: (-best[a["id"]], a["name"])
        )
        return svc.Facts(
            len(hit),
            {"arr": sum(a.get("arr") or 0 for a in hit)},
            [
                {
                    "account_id": a["id"], "name": a["name"], "arr": a.get("arr"),
                    "renewal_date": _date(a.get("renewal_date")), "score": best[a["id"]],
                }
                for a in hit[:limit]
            ],
        )  # fmt: skip

    if plan.question_id == "new_risk_findings":
        new = sorted(
            (
                f
                for f in findings
                if f["type"] == "risk"
                and _after(f["first_seen_at"], since)
                and f["priority_score"] >= p["min_score"]
            ),
            key=lambda f: -f["priority_score"],
        )
        return svc.Facts(
            len(new),
            {
                "accounts": len({f["account_id"] for f in new}),
                "open": sum(1 for f in new if f["status"] in OPEN_FINDINGS),
            },
            [
                {
                    "finding_id": f["id"], "account_id": f["account_id"], "title": f["title"],
                    "account": f["account_name"], "score": f["priority_score"],
                    "first_seen": _date(f["first_seen_at"]), "open": f["status"] in OPEN_FINDINGS,
                }
                for f in new[:limit]
            ],
        )  # fmt: skip

    if plan.question_id == "renewals_due":
        today, risky = now.date(), _at_risk(findings)
        due = sorted(
            (
                a
                for a in accounts
                if (d := _date(a.get("renewal_date"))) is not None
                and today <= d <= today + timedelta(days=p["days"])
            ),
            key=lambda a: (a["renewal_date"], a["name"]),
        )
        return svc.Facts(
            len(due),
            {
                "arr": sum(a.get("arr") or 0 for a in due),
                "at_risk": sum(1 for a in due if a["id"] in risky),
            },
            [
                {
                    "account_id": a["id"], "name": a["name"], "arr": a.get("arr"),
                    "renewal_date": _date(a["renewal_date"]), "at_risk": a["id"] in risky,
                }
                for a in due[:limit]
            ],
        )  # fmt: skip

    if plan.question_id == "pending_approvals":
        waiting = sorted(
            (c for c in cards if c["status"] == "pending_approval"), key=lambda c: c["created_at"]
        )
        oldest = _ts(waiting[0]["created_at"]) if waiting else None
        return svc.Facts(
            len(waiting),
            {"oldest_days": (now - oldest).days} if oldest else {},
            [
                {
                    "card_id": c["id"], "account_id": c["account_id"], "title": c["title"],
                    "account": c["account_name"], "created_at": _ts(c["created_at"]),
                }
                for c in waiting[:limit]
            ],
        )  # fmt: skip

    if plan.question_id == "expansion_opportunities":
        opps = sorted(
            (f for f in findings if f["type"] == "expansion" and f["status"] in OPEN_FINDINGS),
            key=lambda f: -f["priority_score"],
        )
        return svc.Facts(
            len(opps),
            {"value": sum(f.get("value_at_stake") or 0 for f in opps)},
            [
                {
                    "finding_id": f["id"], "account_id": f["account_id"], "title": f["title"],
                    "account": f["account_name"], "value": f.get("value_at_stake"),
                    "score": f["priority_score"],
                }
                for f in opps[:limit]
            ],
        )  # fmt: skip

    if plan.question_id == "decisions_summary":
        decided = [c for c in cards if _after(c.get("decided_at"), since)]
        approved = sum(1 for c in decided if _approved(c))
        rejected = sum(1 for c in decided if c["status"] == "rejected")
        return svc.Facts(
            approved + rejected,
            {
                "approved": approved,
                "rejected": rejected,
                "edited": sum(1 for c in decided if _edited(c)),
            },
        )

    quiet = sorted(
        (a for a in accounts if not _after(a.get("last_activity_at"), since)),
        key=lambda a: (a.get("last_activity_at") or "", a["name"]),
    )
    return svc.Facts(
        len(quiet),
        {},
        [
            {
                "account_id": a["id"], "name": a["name"], "arr": a.get("arr"),
                "last_activity_at": _ts(a.get("last_activity_at")),
            }
            for a in quiet[:limit]
        ],
    )  # fmt: skip


@mock("assistant_catalog")
def m_catalog(request: Request, **_: Any) -> Any:
    return svc.catalog()


@mock("assistant_ask")
def m_ask(request: Request, body: Any, **_: Any) -> Any:
    now = utcnow()
    plan = svc.resolve(body)
    if plan is None:
        return svc.unsupported(now)
    return svc.compose(plan, _facts(plan, now), store().d["org"]["currency"], now)
