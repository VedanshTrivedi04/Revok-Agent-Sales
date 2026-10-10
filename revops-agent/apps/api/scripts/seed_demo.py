"""Idempotent demo seed: orgs "Demo SaaS" and "Other Co", users of every role, the agent.md
section 8 accounts, findings with evidence, contradictions and unknowns, and action cards in
EVERY status. Same dataset as the mock API (app/mocks/data.py), so FE and BE agree on ids.

Run: uv run python scripts/seed_demo.py     (needs `make up && make migrate`)
Safe to re-run: rows are inserted with ON CONFLICT DO NOTHING; the decision log is only written
once per org (it is append-only and hash-chained).
"""

import asyncio
import hashlib
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_engine, org_session  # noqa: E402
from app.mocks import data as D  # noqa: E402
from app.models import actions, audit, brain, integrations, tenancy, timeline  # noqa: E402
from app.services.decision_log import log  # noqa: E402
from app.utils.idempotency import card_idempotency_key  # noqa: E402

ORG = UUID(D.ORG_ID)
OTHER = UUID(D.OTHER_ORG_ID)


def demo_api_key(key_id: str) -> str:
    """Documented synthetic demo API key (never a real secret): rk_live_demo_<id without dashes>."""
    return "rk_live_demo_" + key_id.replace("-", "")


def U(v: str | None) -> UUID | None:
    return UUID(v) if v else None


def dt(v: str | None) -> datetime | None:
    return datetime.fromisoformat(v.replace("Z", "+00:00")) if v else None


def dd(v: str | None) -> date | None:
    return date.fromisoformat(v) if v else None


async def put(s: Any, model: type[Base], rows: list[dict[str, Any]]) -> None:
    if rows:
        await s.execute(insert(model).values(rows).on_conflict_do_nothing())


async def seed_other_org() -> None:
    owner, member = D.uid("other:user:owner"), D.uid("other:user:member")
    async with org_session(OTHER) as s:
        await put(
            s,
            tenancy.Organization,
            [
                {
                    "id": OTHER,
                    "name": D.OTHER_ORG_NAME,
                    "slug": "other-co",
                    "status": "suspended",
                    "primary_domain": "other-co.example.com",
                }
            ],
        )
        await put(s, tenancy.User, [
            {"id": U(owner), "email": "owner@other-co.example.com", "name": "Otto Owner"},
            {"id": U(member), "email": "member@other-co.example.com", "name": "Mia Member"},
        ])  # fmt: skip
        await put(s, tenancy.Membership, [
            {"id": U(D.uid("other:m:owner")), "org_id": OTHER, "user_id": U(owner), "role": "owner"},
            {"id": U(D.uid("other:m:member")), "org_id": OTHER, "user_id": U(member), "role": "member"},
        ])  # fmt: skip
        acc = U(D.uid("other:account:1"))
        await put(s, timeline.Account, [{"id": acc, "org_id": OTHER, "name": "Wayne Tech", "domains": ["wayne.example.com"], "arr": 90000, "status": "active", "renewal_date": date(2026, 12, 1), "risk_level": "high", "priority_score": 70}])  # fmt: skip
        await s.flush()
        await put(s, brain.Finding, [{"id": U(D.uid("other:finding:1")), "org_id": OTHER, "account_id": acc, "type": "risk", "fingerprint": "other:1", "status": "open", "severity": "high", "priority_score": 70, "confidence": 0.7, "title": "Other Co finding (must never be visible to Demo SaaS)", "rule_keys": ["R01_usage_drop"], "categories": ["usage"]}])  # fmt: skip


async def seed_demo_org() -> dict[str, int]:
    S = D.build_files()
    async with org_session(ORG) as s:
        await put(s, tenancy.Organization, [{"id": ORG, "name": D.ORG_NAME, "slug": "demo-saas", "primary_domain": "demo-saas.example.com", "status": "active", "timezone": "Asia/Kolkata", "currency": "USD", "plan": "pilot", "settings": S["org.json"]["settings"]}])  # fmt: skip
        await put(s, tenancy.User, [{"id": U(D.USER_IDS[r]), "email": e, "name": n, "is_superadmin": r == "owner"} for r, (n, e) in D.USERS.items()])  # fmt: skip
        await put(s, tenancy.Membership, [
            {"id": U(D.uid(f"membership:{r}")), "org_id": ORG, "user_id": U(D.USER_IDS[r]), "role": r, "status": "active", "crm_owner_id": f"hs-owner-{i}", "slack_user_id": m["slack_user_id"]}
            for i, (r, m) in enumerate(zip(D.USERS, S["members.json"]["members"], strict=True), 1)
        ])  # fmt: skip
        await put(s, tenancy.Invite, [{"id": U(i["id"]), "org_id": ORG, "email": i["email"], "role": i["role"], "token_hash": hashlib.sha256(i["id"].encode()).hexdigest(), "invited_by": U(i["invited_by"]), "expires_at": dt(i["expires_at"]), "created_at": dt(i["created_at"])} for i in S["members.json"]["invites"]])  # fmt: skip
        await put(s, tenancy.ApiKey, [{"id": U(k["id"]), "org_id": ORG, "name": k["name"], "prefix": k["prefix"], "key_hash": hashlib.sha256(demo_api_key(k["id"]).encode()).hexdigest(), "scopes": k["scopes"], "last_used_at": dt(k["last_used_at"]), "revoked_at": dt(k["revoked_at"])} for k in S["members.json"]["api_keys"]])  # fmt: skip
        fm = S["integrations.json"]["field_mapping"]
        await put(s, integrations.FieldMapping, [{"org_id": ORG, **{k: v for k, v in fm.items() if k not in ("updated_at", "updated_by")}}])  # fmt: skip
        await put(s, integrations.Integration, [{"id": U(i["id"]), "org_id": ORG, "provider": i["provider"], "scope_level": i["scope_level"], "user_id": U(i["user_id"]), "status": i["status"], "external_account_label": i["external_account_label"], "scopes": i["scopes"], "last_sync_at": dt(i["last_sync_at"]), "last_success_at": dt(i["last_success_at"]), "last_error": i["last_error"]} for i in S["integrations.json"]["integrations"]])  # fmt: skip
        await s.flush()
        await put(s, integrations.SyncRun, [{"id": U(r["id"]), "org_id": ORG, "integration_id": U(r["integration_id"]), "started_at": dt(r["started_at"]), "finished_at": dt(r["finished_at"]), "status": r["status"], "stats": r["stats"], "error": r["error"]} for r in S["integrations.json"]["sync_runs"]])  # fmt: skip
        await put(s, actions.AutonomyPolicy, [{"id": U(D.uid(f"policy:{p['action_type']}")), "org_id": ORG, "action_type": p["action_type"], "tier": p["tier"], "conditions": p["conditions"], "locked": p["locked"]} for p in S["ops.json"]["autonomy"]])  # fmt: skip

        # ---- accounts and their timeline
        owners = {k: v[7] for k, v in D.ACCOUNTS.items()}
        acc_rows = []
        for a in S["accounts.json"]["list"]:
            key = next(k for k, v in D.ACC.items() if v == a["id"])
            acc_rows.append({"id": U(a["id"]), "org_id": ORG, "name": a["name"], "domains": a["domains"], "external_ids": {"hubspot": f"hs-{key}"}, "owner_user_id": U(D.USER_IDS[owners[key]]), "crm_owner_id": f"hs-owner-{key}", "arr": a["arr"], "plan_name": a["plan_name"], "seats_purchased": a["seats_purchased"], "renewal_date": dd(a["renewal_date"]), "lifecycle_stage": "customer", "crm_health": a["crm_health"], "status": a["status"], "risk_level": a["risk_level"], "priority_score": a["priority_score"], "last_activity_at": dt(a["last_activity_at"]), "crm_url": a["crm_url"]})  # fmt: skip
        await put(s, timeline.Account, acc_rows)
        await s.flush()
        for key, contacts in S["accounts.json"]["contacts"].items():
            await put(s, timeline.Contact, [{"id": U(c["id"]), "org_id": ORG, "account_id": U(D.ACC[key]), "external_id": f"hs-c-{c['id'][:8]}", "name": c["name"], "email": c["email"], "title": c["title"], "role_tags": c["role_tags"], "is_active": c["is_active"], "last_inbound_at": dt(c["last_inbound_at"]), "last_outbound_at": dt(c["last_outbound_at"])} for c in contacts])  # fmt: skip
        for key, deals in S["accounts.json"]["deals"].items():
            await put(s, timeline.Deal, [{"id": U(d["id"]), "org_id": ORG, "account_id": U(D.ACC[key]), "external_id": f"hs-d-{key}", "name": d["name"], "pipeline": "default", "stage": "negotiation", "stage_label": d["stage_label"], "amount": d["amount"], "close_date": dd(d["close_date"]), "deal_type": d["deal_type"], "next_step": d["next_step"], "is_closed": d["is_closed"]} for d in deals])  # fmt: skip
        for key, events in S["accounts.json"]["timeline"].items():
            await put(s, timeline.Event, [{"id": U(e["id"]), "org_id": ORG, "account_id": U(D.ACC[key]), "source": e["source"], "source_record_id": e["id"], "type": e["type"], "occurred_at": dt(e["occurred_at"]), "title": e["title"], "participants": e["participants"], "match_method": "contact_email", "match_confidence": 0.95} for e in events])  # fmt: skip
        for key, series in S["accounts.json"]["usage"].items():
            await put(s, timeline.UsageSnapshot, [{"id": U(D.uid(f"usage:{key}:{p['period_start']}")), "org_id": ORG, "account_id": U(D.ACC[key]), "period_start": dd(p["period_start"]), "period_end": dd(p["period_end"]), "granularity": "week", "active_users": p["active_users"], "seats_used": p["seats_used"], "logins": p["logins"], "key_events": p["key_events"], "source": "api"} for p in series["points"]])  # fmt: skip
        review_events = [{"id": U(r["event_id"]), "org_id": ORG, "account_id": None, "source": "gmail", "source_record_id": r["event_id"], "type": "email_in", "occurred_at": dt(r["created_at"]), "title": r["event_title"], "match_method": "none", "match_confidence": 0} for r in S["ops.json"]["entity_reviews"]]  # fmt: skip
        await put(s, timeline.Event, review_events)
        await s.flush()
        await put(s, timeline.EntityMatchReview, [{"id": U(r["id"]), "org_id": ORG, "event_id": U(r["event_id"]), "candidate_account_ids": [U(c) for c in r["candidate_account_ids"]], "reason": r["reason"], "status": r["status"]} for r in S["ops.json"]["entity_reviews"]])  # fmt: skip

        # ---- brain: runs, findings, evidence, rule hits
        runs = S["ops.json"]["runs"]
        await put(s, brain.AgentRun, [{"id": U(r["id"]), "org_id": ORG, "account_id": U(r["account_id"]), "trigger": r["trigger"], "status": r["status"], "started_at": dt(r["started_at"]), "finished_at": dt(r["finished_at"]), "stats": r["stats"], "model": r["model"], "error": r["error"]} for r in runs])  # fmt: skip
        await s.flush()
        run_of = {r["account_id"]: U(r["id"]) for r in runs}
        for f in S["findings.json"]:
            keys = [h["rule_key"] for h in f["rule_hits"]]
            await put(s, brain.Finding, [{"id": U(f["id"]), "org_id": ORG, "account_id": U(f["account_id"]), "type": f["type"], "fingerprint": f"{f['type']}:{f['account_id']}:{','.join(keys) or f['id']}", "status": f["status"], "severity": f["severity"], "priority_score": f["priority_score"], "confidence": f["confidence"], "title": f["title"], "summary": f["summary"], "claims": f["claims"], "unknowns": f["unknowns"], "contradictions": f["contradictions"], "rule_keys": keys, "categories": sorted({h["category"] for h in f["rule_hits"]}), "value_at_stake": f["value_at_stake"], "renewal_in_days": f["renewal_in_days"], "first_seen_at": dt(f["first_seen_at"]), "last_seen_at": dt(f["last_seen_at"]), "dismissed_reason": f["dismissed_reason"], "agent_run_id": run_of.get(f["account_id"]), "model": f["model"], "prompt_version": f["prompt_version"]}])  # fmt: skip
            await s.flush()
            await put(s, brain.FindingEvidence, [{"id": U(D.uid(f"evidence:{f['id']}:{e['key']}")), "org_id": ORG, "finding_id": U(f["id"]), "evidence_key": e["key"], "kind": e["kind"], "label": e["label"], "detail": e["detail"], "source": e["source"], "source_url": e["source_url"], "occurred_at": dt(e["occurred_at"])} for e in f["evidence"]])  # fmt: skip
            await put(s, brain.RuleHit, [{"id": U(D.uid(f"rulehit:{f['id']}:{h['rule_key']}")), "org_id": ORG, "account_id": U(f["account_id"]), "agent_run_id": run_of.get(f["account_id"]), "rule_key": h["rule_key"], "category": h["category"], "finding_type": f["type"], "severity_points": 2, "metrics": h["metrics"]} for h in f["rule_hits"]])  # fmt: skip

        # ---- cards in every status (+ execution rows)
        cards = S["cards.json"]
        await put(s, actions.ActionCard, [{"id": U(c["id"]), "org_id": ORG, "account_id": U(c["account_id"]), "finding_id": U(c["finding_id"]), "type": c["type"], "tier": c["tier"], "status": c["status"], "title": c["title"], "rationale": c["rationale"], "evidence_keys": c["evidence_keys"], "payload": c["payload"], "edited_payload": c["edited_payload"], "preview": c["preview"], "assignee_user_id": U(c["assignee_user_id"]), "decided_by": U(c["decided_by"]), "decided_at": dt(c["decided_at"]), "decision_channel": c["decision_channel"], "rejection_reason": c["rejection_reason"], "rejection_note": c["rejection_note"], "idempotency_key": card_idempotency_key(ORG, U(c["account_id"]), c["type"], U(c["finding_id"]), {"seed": c["id"]}), "external_ref": c["external_ref"], "executed_at": dt(c["executed_at"]), "reverted_at": dt(c["reverted_at"]), "expires_at": dt(c["expires_at"]), "error": c["error"], "created_at": dt(c["created_at"])} for c in cards])  # fmt: skip
        await s.flush()
        await put(s, actions.Execution, [{"id": U(D.uid(f"exec:{c['id']}")), "org_id": ORG, "action_card_id": U(c["id"]), "attempt": 1, "status": "failed" if c["status"] == "failed" else ("started" if c["status"] == "executing" else "succeeded"), "request": {"type": c["type"]}, "response": c["external_ref"], "started_at": dt(c["created_at"]), "finished_at": None if c["status"] == "executing" else dt(c["created_at"]), "error": c["error"] if c["status"] == "failed" else None} for c in cards if c["status"] in ("executing", "executed", "reverted", "failed")])  # fmt: skip
        await put(s, audit.Notification, [{"id": U(n["id"]), "org_id": ORG, "user_id": U(D.PRIYA), "kind": n["kind"], "title": n["title"], "body": n["body"], "link": n["link"], "read_at": dt(n["read_at"]), "created_at": dt(n["created_at"])} for n in S["notifications.json"]])  # fmt: skip
        await put(s, audit.FeatureFlag, [{"key": f["key"], "default": f["default"], "per_org": f["per_org"]} for f in S["admin.json"]["flags"]])  # fmt: skip
        await s.flush()

        # ---- decision log: once per org (append-only, hash-chained)
        existing = (
            await s.execute(select(func.count()).select_from(audit.DecisionLog))
        ).scalar_one()
        if existing == 0:
            for e in sorted(S["log.json"], key=lambda x: x["id"]):
                await log(s, org_id=ORG, actor_type=e["actor_type"], actor_id=e["actor_id"], event=e["event"], entity_type=e["entity_type"], entity_id=U(e["entity_id"]), account_id=U(e["account_id"]), data={"summary": e["summary"], "seed": True})  # fmt: skip

        counts = {}
        for name, model in {
            "accounts": timeline.Account,
            "findings": brain.Finding,
            "cards": actions.ActionCard,
            "log": audit.DecisionLog,
            "members": tenancy.Membership,
        }.items():
            counts[name] = (await s.execute(select(func.count()).select_from(model))).scalar_one()
    return counts


async def seed_demo() -> dict[str, int]:
    await seed_other_org()
    return await seed_demo_org()


async def main() -> None:
    counts = await seed_demo()
    await get_engine().dispose()
    print("seeded Demo SaaS:", ", ".join(f"{k}={v}" for k, v in counts.items()))
    print("login ids (service JWT sub):", {r: D.USER_IDS[r] for r in D.USERS})
    print("org_id:", D.ORG_ID)


if __name__ == "__main__":
    asyncio.run(main())
