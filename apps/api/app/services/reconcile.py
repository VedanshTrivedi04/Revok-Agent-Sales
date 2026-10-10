"""Live reconciliation of our data against the providers (accuracy gates P2/P5).

hubspot: counts of companies/contacts/deals in the DB vs HubSpot, duplicate external ids, and a
field-by-field spot check of N random accounts on the org's mapped properties.
gmail: message count in the sync window vs stored events (we intentionally store only messages
with an external participant, so stored <= total), duplicates, and a spot check that N stored
events still exist in Gmail.

Both need a connected integration (they call the real provider through ConnCtx), so they run from
scripts/reconcile_hubspot.py and scripts/reconcile_gmail.py, not in CI. Logic is unit-tested with
mocked HTTP.
"""

import random
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from app.connectors.ctx import ConnCtx
from app.connectors.hubspot.writes import HS_BASE
from app.db.session import org_session
from app.models.integrations import FieldMapping
from app.models.timeline import Account, Contact, Deal, Event
from app.utils.time import utcnow

GMAIL_BASE = "https://gmail.googleapis.com"


def _num(v: Any) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


async def reconcile_hubspot(org_id: UUID, integration_id: UUID, *, sample: int = 20) -> dict[str, Any]:
    ctx = await ConnCtx.load(org_id, integration_id)
    report: dict[str, Any] = {"counts": {}, "duplicates": {}, "spot_check": {"checked": 0, "mismatches": []}}

    async with org_session(org_id) as s:
        db_counts = {
            "companies": await s.scalar(select(func.count()).select_from(Account).where(Account.status != "archived")) or 0,
            "contacts": await s.scalar(select(func.count()).select_from(Contact)) or 0,
            "deals": await s.scalar(select(func.count()).select_from(Deal)) or 0,
        }
        dup = (
            await s.execute(
                select(Account.external_ids["hubspot"].astext, func.count())
                .where(Account.external_ids["hubspot"].astext.is_not(None))
                .group_by(Account.external_ids["hubspot"].astext)
                .having(func.count() > 1)
            )
        ).all()
        mapping = (await s.execute(select(FieldMapping))).scalar_one_or_none()
        accounts = (
            (await s.execute(select(Account).where(Account.external_ids["hubspot"].astext.is_not(None))))
            .scalars()
            .all()
        )
    report["duplicates"] = {"accounts_by_hubspot_id": len(dup)}

    for obj in ("companies", "contacts", "deals"):
        resp = await ctx.request(
            "POST", f"{HS_BASE}/crm/v3/objects/{obj}/search", json={"limit": 1, "filterGroups": []}
        )
        total = int(resp.json().get("total", 0))  # type: ignore[attr-defined]
        report["counts"][obj] = {"db": db_counts[obj], "hubspot": total, "match": db_counts[obj] == total}

    props = ["name", "domain"]
    mapped: dict[str, str | None] = {
        "arr": getattr(mapping, "arr_property", None),
        "renewal_date": getattr(mapping, "renewal_date_property", None),
        "seats": getattr(mapping, "seats_property", None),
        "health": getattr(mapping, "health_property", None),
    }
    props += [p for p in mapped.values() if p]
    for acc in random.sample(accounts, min(sample, len(accounts))):
        hid = acc.external_ids["hubspot"]
        resp = await ctx.request(
            "GET", f"{HS_BASE}/crm/v3/objects/companies/{hid}", params={"properties": ",".join(props)}
        )
        hp = resp.json().get("properties", {})  # type: ignore[attr-defined]
        checks = {
            "name": (acc.name, hp.get("name") or "Unnamed Company"),
            "arr": (float(acc.arr) if acc.arr is not None else None, _num(hp.get(mapped["arr"] or ""))),
            "renewal_date": (acc.renewal_date.isoformat() if acc.renewal_date else None, (hp.get(mapped["renewal_date"] or "") or "")[:10] or None),
            "seats": (acc.seats_purchased, int(_num(hp.get(mapped["seats"] or "")) or 0) or None),
            "health": (acc.crm_health, hp.get(mapped["health"] or "") or None),
        }  # fmt: skip
        for field, (ours, theirs) in checks.items():
            if field != "name" and not mapped.get(field):
                continue  # not mapped for this org
            if ours != theirs:
                report["spot_check"]["mismatches"].append({"account": str(acc.id), "field": field, "ours": ours, "hubspot": theirs})
        report["spot_check"]["checked"] += 1

    report["ok"] = (
        all(c["match"] for c in report["counts"].values())
        and not dup
        and not report["spot_check"]["mismatches"]
    )
    return report


async def reconcile_gmail(
    org_id: UUID, integration_id: UUID, user_id: UUID, *, days: int = 180, sample: int = 20
) -> dict[str, Any]:
    ctx = await ConnCtx.load(org_id, integration_id)
    after = int((utcnow() - timedelta(days=days)).timestamp())
    total, token = 0, None
    while True:
        params: dict[str, Any] = {"q": f"after:{after} -in:chats", "maxResults": 500}
        if token:
            params["pageToken"] = token
        body = (await ctx.request("GET", f"{GMAIL_BASE}/gmail/v1/users/me/messages", params=params)).json()  # type: ignore[attr-defined]
        total += len(body.get("messages", []))
        token = body.get("nextPageToken")
        if not token:
            break

    async with org_session(org_id) as s:
        events = (
            (
                await s.execute(
                    select(Event).where(
                        Event.source == "gmail",
                        Event.occurred_at >= utcnow() - timedelta(days=days),
                        Event.raw["user_id"].astext == str(user_id),
                    )
                )
            )
            .scalars()
            .all()
        )
    ids = [e.source_record_id for e in events]
    missing: list[str] = []
    for rid in random.sample(ids, min(sample, len(ids))):
        try:
            await ctx.request("GET", f"{GMAIL_BASE}/gmail/v1/users/me/messages/{rid}", params={"format": "minimal"})
        except Exception:
            missing.append(rid)
    report = {
        "gmail_messages": total,
        "stored_events": len(ids),
        "duplicates": len(ids) - len(set(ids)),
        "stored_not_in_gmail": missing,
        "note": "stored <= gmail_messages is expected: internal-only and bulk mail is not stored",
    }
    report["ok"] = len(ids) <= total and report["duplicates"] == 0 and not missing
    return report
