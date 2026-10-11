import sys
from pathlib import Path
sys.path.insert(0, r"D:\CDGI2026\revops-agent\apps\api")

import asyncio
from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.base import Base
from app.db.session import admin_session, get_engine, org_session
from app.mocks import data as D
from app.models import actions, audit, brain, integrations, tenancy, timeline
from app.services.decision_log import log
from app.utils.idempotency import card_idempotency_key

PRAGYAN_ORG_ID = UUID("01a12aaf-5ea3-7153-91c3-9866a22d91b4")
DEMO_ORG_ID = UUID(D.ORG_ID)

def U(v: str | None) -> UUID | None:
    return UUID(v) if v else None

def dt(v: str | None) -> datetime | None:
    return datetime.fromisoformat(v.replace("Z", "+00:00")) if v else None

def dd(v: str | None) -> date | None:
    return date.fromisoformat(v) if v else None

async def put(s, model, rows):
    if rows:
        await s.execute(insert(model).values(rows).on_conflict_do_nothing())

async def main():
    print("Seeding Pragyan Inovations workspace and linking test@gmail.com...")

    # 1. Get test@gmail.com user
    async with admin_session() as s:
        test_user = (await s.execute(select(tenancy.User).where(tenancy.User.email == "test@gmail.com"))).scalar_one()
        test_user_id = test_user.id

        # Also give test@gmail.com membership in Demo SaaS
        await put(s, tenancy.Membership, [{
            "id": uuid4(),
            "org_id": DEMO_ORG_ID,
            "user_id": test_user_id,
            "role": "owner",
            "status": "active"
        }])
        print(f"Linked test@gmail.com ({test_user_id}) to Demo SaaS.")

    # 2. Seed into Pragyan Inovations
    S = D.build_files()
    async with org_session(PRAGYAN_ORG_ID) as s:
        # Settings & Integrations
        fm = S["integrations.json"]["field_mapping"]
        await put(s, integrations.FieldMapping, [{
            "org_id": PRAGYAN_ORG_ID,
            **{k: v for k, v in fm.items() if k not in ("updated_at", "updated_by")}
        }])
        
        # Integrations
        for item in S["integrations.json"]["integrations"]:
            await put(s, integrations.Integration, [{
                "id": uuid4(),
                "org_id": PRAGYAN_ORG_ID,
                "provider": item["provider"],
                "scope_level": item["scope_level"],
                "user_id": test_user_id if item["scope_level"] == "user" else None,
                "status": "connected",
                "external_account_label": item["external_account_label"],
                "scopes": item["scopes"],
                "last_sync_at": dt(item["last_sync_at"]),
                "last_success_at": dt(item["last_success_at"]),
                "last_error": None
            }])
        await s.flush()

        # Autonomy policies
        for p in S["ops.json"]["autonomy"]:
            await put(s, actions.AutonomyPolicy, [{
                "id": uuid4(),
                "org_id": PRAGYAN_ORG_ID,
                "action_type": p["action_type"],
                "tier": p["tier"],
                "conditions": p["conditions"],
                "locked": p["locked"]
            }])

        # Map accounts to new UUIDs for Pragyan Inovations
        acc_id_map = {}
        for key, old_id in D.ACC.items():
            acc_id_map[key] = uuid4()

        # Accounts
        acc_rows = []
        for a in S["accounts.json"]["list"]:
            key = next(k for k, v in D.ACC.items() if v == a["id"])
            acc_rows.append({
                "id": acc_id_map[key],
                "org_id": PRAGYAN_ORG_ID,
                "name": a["name"],
                "domains": a["domains"],
                "external_ids": {"hubspot": f"hs-{key}"},
                "owner_user_id": test_user_id,
                "crm_owner_id": f"hs-owner-{key}",
                "arr": a["arr"],
                "plan_name": a["plan_name"],
                "seats_purchased": a["seats_purchased"],
                "renewal_date": dd(a["renewal_date"]),
                "lifecycle_stage": "customer",
                "crm_health": a["crm_health"],
                "status": a["status"],
                "risk_level": a["risk_level"],
                "priority_score": a["priority_score"],
                "last_activity_at": dt(a["last_activity_at"]),
                "crm_url": a["crm_url"]
            })
        await put(s, timeline.Account, acc_rows)
        await s.flush()
        print(f"Seeded {len(acc_rows)} accounts.")

        # Contacts & Deals & Timeline & Usage
        for key, contacts in S["accounts.json"]["contacts"].items():
            await put(s, timeline.Contact, [{
                "id": uuid4(),
                "org_id": PRAGYAN_ORG_ID,
                "account_id": acc_id_map[key],
                "external_id": f"hs-c-{c['id'][:8]}",
                "name": c["name"],
                "email": f"{c['name'].lower().replace(' ', '.')}@{key}.example.com",
                "title": c["title"],
                "role_tags": c["role_tags"],
                "is_active": c["is_active"],
                "last_inbound_at": dt(c["last_inbound_at"]),
                "last_outbound_at": dt(c["last_outbound_at"])
            } for c in contacts])

        for key, deals in S["accounts.json"]["deals"].items():
            await put(s, timeline.Deal, [{
                "id": uuid4(),
                "org_id": PRAGYAN_ORG_ID,
                "account_id": acc_id_map[key],
                "external_id": f"hs-d-{key}",
                "name": d["name"],
                "pipeline": "default",
                "stage": "negotiation",
                "stage_label": d["stage_label"],
                "amount": d["amount"],
                "close_date": dd(d["close_date"]),
                "deal_type": d["deal_type"],
                "next_step": d["next_step"],
                "is_closed": d["is_closed"]
            } for d in deals])

        for key, events in S["accounts.json"]["timeline"].items():
            await put(s, timeline.Event, [{
                "id": uuid4(),
                "org_id": PRAGYAN_ORG_ID,
                "account_id": acc_id_map[key],
                "source": e["source"],
                "source_record_id": str(uuid4()),
                "type": e["type"],
                "occurred_at": dt(e["occurred_at"]),
                "title": e["title"],
                "participants": e["participants"],
                "match_method": "contact_email",
                "match_confidence": 0.95
            } for e in events])

        for key, series in S["accounts.json"]["usage"].items():
            await put(s, timeline.UsageSnapshot, [{
                "id": uuid4(),
                "org_id": PRAGYAN_ORG_ID,
                "account_id": acc_id_map[key],
                "period_start": dd(p["period_start"]),
                "period_end": dd(p["period_end"]),
                "granularity": "week",
                "active_users": p["active_users"],
                "seats_used": p["seats_used"],
                "logins": p["logins"],
                "key_events": p["key_events"],
                "source": "api"
            } for p in series["points"]])
        await s.flush()

        # Findings & Evidence & Rule hits
        finding_id_map = {}
        for f in S["findings.json"]:
            old_fid = f["id"]
            new_fid = uuid4()
            finding_id_map[old_fid] = new_fid
            
            # Find matching account
            old_acc_id = f["account_id"]
            key = next(k for k, v in D.ACC.items() if v == old_acc_id)
            new_acc_id = acc_id_map[key]

            keys = [h["rule_key"] for h in f["rule_hits"]]
            await put(s, brain.Finding, [{
                "id": new_fid,
                "org_id": PRAGYAN_ORG_ID,
                "account_id": new_acc_id,
                "type": f["type"],
                "fingerprint": f"{f['type']}:{new_acc_id}:{','.join(keys)}",
                "status": f["status"],
                "severity": f["severity"],
                "priority_score": f["priority_score"],
                "confidence": f["confidence"],
                "title": f["title"],
                "summary": f["summary"],
                "claims": f["claims"],
                "unknowns": f["unknowns"],
                "contradictions": f["contradictions"],
                "rule_keys": keys,
                "categories": sorted({h["category"] for h in f["rule_hits"]}),
                "value_at_stake": f["value_at_stake"],
                "renewal_in_days": f["renewal_in_days"],
                "first_seen_at": dt(f["first_seen_at"]),
                "last_seen_at": dt(f["last_seen_at"]),
                "dismissed_reason": f["dismissed_reason"],
                "agent_run_id": None,
                "model": f["model"],
                "prompt_version": f["prompt_version"]
            }])
            await s.flush()

            for e in f["evidence"]:
                await put(s, brain.FindingEvidence, [{
                    "id": uuid4(),
                    "org_id": PRAGYAN_ORG_ID,
                    "finding_id": new_fid,
                    "evidence_key": e["key"],
                    "kind": e["kind"],
                    "label": e["label"],
                    "detail": e["detail"],
                    "source": e["source"],
                    "source_url": e["source_url"],
                    "occurred_at": dt(e["occurred_at"])
                }])

            for h in f["rule_hits"]:
                await put(s, brain.RuleHit, [{
                    "id": uuid4(),
                    "org_id": PRAGYAN_ORG_ID,
                    "account_id": new_acc_id,
                    "agent_run_id": None,
                    "rule_key": h["rule_key"],
                    "category": h["category"],
                    "finding_type": f["type"],
                    "severity_points": 2,
                    "metrics": h["metrics"]
                }])
        print(f"Seeded {len(S['findings.json'])} findings & evidence.")

        # Action cards
        cards = S["cards.json"]
        for c in cards:
            old_fid = c["finding_id"]
            new_fid = finding_id_map.get(old_fid, uuid4())
            old_acc_id = c["account_id"]
            key = next(k for k, v in D.ACC.items() if v == old_acc_id)
            new_acc_id = acc_id_map[key]
            card_id = uuid4()

            await put(s, actions.ActionCard, [{
                "id": card_id,
                "org_id": PRAGYAN_ORG_ID,
                "account_id": new_acc_id,
                "finding_id": new_fid,
                "type": c["type"],
                "tier": c["tier"],
                "status": c["status"],
                "title": c["title"],
                "rationale": c["rationale"],
                "evidence_keys": c["evidence_keys"],
                "payload": c["payload"],
                "edited_payload": c["edited_payload"],
                "preview": c["preview"],
                "assignee_user_id": test_user_id,
                "decided_by": test_user_id if c["decided_by"] else None,
                "decided_at": dt(c["decided_at"]),
                "decision_channel": c["decision_channel"],
                "rejection_reason": c["rejection_reason"],
                "rejection_note": c["rejection_note"],
                "idempotency_key": card_idempotency_key(PRAGYAN_ORG_ID, new_acc_id, c["type"], new_fid, {"seed": str(card_id)}),
                "external_ref": c["external_ref"],
                "executed_at": dt(c["executed_at"]),
                "reverted_at": dt(c["reverted_at"]),
                "expires_at": dt(c["expires_at"]),
                "error": c["error"],
                "created_at": dt(c["created_at"])
            }])

        # Notifications
        for n in S["notifications.json"]:
            await put(s, audit.Notification, [{
                "id": uuid4(),
                "org_id": PRAGYAN_ORG_ID,
                "user_id": test_user_id,
                "kind": n["kind"],
                "title": n["title"],
                "body": n["body"],
                "link": n["link"],
                "read_at": dt(n["read_at"]),
                "created_at": dt(n["created_at"])
            }])
        await s.flush()
        print(f"Seeded {len(cards)} action cards.")

        # Decision log
        for e in sorted(S["log.json"], key=lambda x: x["id"]):
            acc_id = None
            if e.get("account_id"):
                matching_key = next((k for k, v in D.ACC.items() if v == e["account_id"]), None)
                if matching_key:
                    acc_id = acc_id_map.get(matching_key)
            await log(
                s,
                org_id=PRAGYAN_ORG_ID,
                actor_type=e["actor_type"],
                actor_id=test_user_id,
                event=e["event"],
                entity_type=e["entity_type"],
                entity_id=acc_id or PRAGYAN_ORG_ID,
                account_id=acc_id,
                data={"summary": e["summary"], "seed": True}
            )
        print("Decision log populated.")

    await get_engine().dispose()
    print("SUCCESS: Pragyan Inovations fully seeded with live demo accounts, findings, cards, and decision log!")

if __name__ == "__main__":
    asyncio.run(main())
