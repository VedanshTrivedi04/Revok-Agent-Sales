"""Mock API (MOCK_API=true): realistic, stateful-in-memory responses. Never writes to the DB.

Fixtures live in app/mocks/*.json (generated from app/mocks/data.py). State is per process and
resets on restart (or via reset_store() in tests). Headers:
  X-Mock-Error: <code>   -> respond with that registered error code (status from the registry)
  X-Mock-Empty: true     -> lists/pages come back empty (empty-state UI)
"""

import asyncio
import copy
import json
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import ValidationError

from app.auth.deps import current_membership, get_claims
from app.config import get_settings
from app.mocks import data as D
from app.permissions import permissions_for
from app.schemas.action_payloads import ACTION_PAYLOADS
from app.utils.errors import ERROR_CODES, AppError
from app.utils.pagination import PageParams, decode_cursor, encode_cursor

MOCK_DIR = Path(__file__).parent
Handler = Callable[..., Awaitable[Any] | Any]
HANDLERS: dict[str, Handler] = {}
FILES = (
    "org users accounts findings cards log members integrations notifications ops admin"
).split()


def mock(opid: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        HANDLERS[opid] = fn
        return fn

    return deco


class Store:
    def __init__(self) -> None:
        self.d: dict[str, Any] = {
            name: json.loads((MOCK_DIR / f"{name}.json").read_text(encoding="utf-8"))
            for name in FILES
        }
        self.log_seq = max(e["id"] for e in self.d["log"])
        self.flags_state: dict[str, Any] = {}


_STORE: Store | None = None


def store() -> Store:
    global _STORE
    if _STORE is None:
        _STORE = Store()
    return _STORE


def reset_store() -> None:
    global _STORE
    _STORE = None


def now() -> str:
    return D.ts()


def not_found(what: str) -> AppError:
    return AppError("not_found", f"{what} not found")


def page_of(items: list[Any], page: PageParams) -> dict[str, Any]:
    start = decode_cursor(page.cursor, 1)[0] if page.cursor else 0
    chunk = items[start : start + page.limit]
    more = start + page.limit < len(items)
    return {"items": chunk, "next_cursor": encode_cursor([start + page.limit]) if more else None}


async def actor(request: Request) -> dict[str, Any]:
    """(user_id, role) of the caller; falls back to the demo member when unauthenticated."""
    try:
        claims = get_claims(request)
    except AppError:
        return {
            "id": D.PRIYA,
            "role": "member",
            "email": D.USERS["member"][1],
            "name": "Priya Member",
        }
    role = "member"
    try:
        role = (await current_membership(claims)).role.value
    except AppError:
        pass
    name = D.USERS.get(role, ("Demo User", ""))[0]
    return {
        "id": str(claims.user_id),
        "role": role,
        "email": claims.email or D.USERS[role][1],
        "name": name,
    }


def is_demo_user(user_id: str) -> bool:
    return user_id in D.USER_IDS.values()


def log_event(
    event: str, etype: str, entity_id: str, account_id: str | None, actor_id: str, summary: str
) -> None:
    s = store()
    s.log_seq += 1
    s.d["log"].append(
        {"id": s.log_seq, "ts": now(), "actor_type": "user", "actor_id": actor_id, "actor_name": None,
         "event": event, "entity_type": etype, "entity_id": entity_id, "account_id": account_id, "summary": summary}
    )  # fmt: skip


async def serve_mock(opid: str, request: Request, kwargs: dict[str, Any]) -> Any:
    err = request.headers.get("x-mock-error")
    if err:
        status, message = ERROR_CODES.get(err, (400, "Unknown mock error code"))
        raise AppError(
            err if err in ERROR_CODES else "bad_request", message, status, {"mock": True}
        )
    handler = HANDLERS.get(opid)
    if handler is None:
        raise AppError("not_implemented", f"No mock for {opid}")
    result = handler(request=request, **kwargs)
    if asyncio.iscoroutine(result):
        result = await result
    if request.headers.get("x-mock-empty", "").lower() == "true":
        result = _empty(result)
    return result


def _empty(result: Any) -> Any:
    if isinstance(result, dict) and "items" in result:
        return {**result, "items": [], "next_cursor": None}
    if isinstance(result, list):
        return []
    if isinstance(result, dict) and "points" in result:
        return {**result, "points": [], "baseline": None}
    if isinstance(result, dict) and "generated_at" in result:
        return {**result, "items": [], "counts": {"risk": 0, "expansion": 0, "pending_cards": 0}}
    return result


# ============================================================ identity
async def _me(request: Request) -> dict[str, Any]:
    a = await actor(request)
    s = store().d
    org = s["org"]
    user = {"id": a["id"], "email": a["email"], "name": a["name"], "avatar_url": None, "timezone": "Asia/Kolkata",
            "notification_prefs": store().flags_state.get(f"prefs:{a['id']}", {})}  # fmt: skip
    return {
        "user": user,
        "memberships": [{"org_id": org["id"], "org_name": org["name"], "role": a["role"]},
                        {"org_id": D.OTHER_ORG_ID, "org_name": D.OTHER_ORG_NAME, "role": "viewer"}],
        "org": {k: org[k] for k in ("id", "name", "status", "plan", "timezone", "currency")},
        "role": a["role"], "permissions": permissions_for(a["role"]),
        "flags": {f["key"]: f["default"] for f in s["admin"]["flags"]},
        "onboarding": org["onboarding"],
    }  # fmt: skip


@mock("get_me")
async def m_get_me(request: Request, **_: Any) -> Any:
    return await _me(request)


@mock("patch_me")
async def m_patch_me(request: Request, body: Any, **_: Any) -> Any:
    a = await actor(request)
    if body.notification_prefs is not None:
        store().flags_state[f"prefs:{a['id']}"] = body.notification_prefs.model_dump()
    return await _me(request)


@mock("create_org")
def m_create_org(request: Request, body: Any, **_: Any) -> Any:
    return {**store().d["org"], "id": str(uuid4()), "name": body.name, "slug": None,
            "primary_domain": body.primary_domain, "timezone": body.timezone, "currency": body.currency}  # fmt: skip


@mock("get_current_org")
def m_get_org(request: Request, **_: Any) -> Any:
    return store().d["org"]


@mock("patch_current_org")
def m_patch_org(request: Request, body: Any, **_: Any) -> Any:
    org = store().d["org"]
    org.update(body.model_dump(exclude_none=True))
    return org


@mock("delete_current_org")
def m_delete_org(request: Request, body: Any, **_: Any) -> Any:
    if body.confirm != store().d["org"]["name"]:
        raise AppError("validation_error", "Type the organization name to confirm")
    return {"ok": True, "detail": {}}


@mock("get_onboarding")
def m_onboarding(request: Request, **_: Any) -> Any:
    return store().d["org"]["onboarding"]


# ============================================================ members, invites, keys
@mock("list_members")
def m_list_members(request: Request, page: PageParams, **_: Any) -> Any:
    return page_of(store().d["members"]["members"], page)


@mock("patch_member")
def m_patch_member(request: Request, member_id: Any, body: Any, **_: Any) -> Any:
    m = next((x for x in store().d["members"]["members"] if x["id"] == str(member_id)), None)
    if m is None:
        raise not_found("Member")
    if body.role and m["role"] == "owner" and body.role != "owner":
        if sum(1 for x in store().d["members"]["members"] if x["role"] == "owner") == 1:
            raise AppError("last_owner_required")
    m.update(body.model_dump(exclude_none=True))
    return m


@mock("remove_member")
def m_remove_member(request: Request, member_id: Any, **_: Any) -> Any:
    ms = store().d["members"]["members"]
    m = next((x for x in ms if x["id"] == str(member_id)), None)
    if m is None:
        raise not_found("Member")
    if m["role"] == "owner" and sum(1 for x in ms if x["role"] == "owner") == 1:
        raise AppError("last_owner_required")
    ms.remove(m)
    return {"ok": True, "detail": {}}


@mock("create_invite")
async def m_create_invite(request: Request, body: Any, **_: Any) -> Any:
    a = await actor(request)
    inv = {"id": str(uuid4()), "email": str(body.email), "role": body.role, "invited_by": a["id"],
           "expires_at": D.ts(days_ago=-7), "created_at": now()}  # fmt: skip
    store().d["members"]["invites"].append(inv)
    return inv


@mock("list_invites")
def m_list_invites(request: Request, page: PageParams, **_: Any) -> Any:
    return page_of(store().d["members"]["invites"], page)


@mock("revoke_invite")
def m_revoke_invite(request: Request, invite_id: Any, **_: Any) -> Any:
    invs = store().d["members"]["invites"]
    inv = next((x for x in invs if x["id"] == str(invite_id)), None)
    if inv is None:
        raise not_found("Invite")
    invs.remove(inv)
    return {"ok": True, "detail": {}}


@mock("accept_invite")
def m_accept_invite(request: Request, body: Any, **_: Any) -> Any:
    if body.token == "expired":
        raise AppError("bad_request", "Invite expired or already used")
    return {"org_id": D.ORG_ID, "role": "member"}


@mock("list_api_keys")
def m_list_keys(request: Request, **_: Any) -> Any:
    return store().d["members"]["api_keys"]


@mock("create_api_key")
def m_create_key(request: Request, body: Any, **_: Any) -> Any:
    key = "rk_live_" + secrets.token_urlsafe(24)
    row = {"id": str(uuid4()), "name": body.name, "prefix": key[:8], "scopes": body.scopes,
           "last_used_at": None, "revoked_at": None, "created_at": now()}  # fmt: skip
    store().d["members"]["api_keys"].append(row)
    return {**row, "key": key}


@mock("revoke_api_key")
def m_revoke_key(request: Request, key_id: Any, **_: Any) -> Any:
    k = next((x for x in store().d["members"]["api_keys"] if x["id"] == str(key_id)), None)
    if k is None:
        raise not_found("API key")
    k["revoked_at"] = now()
    return {"ok": True, "detail": {}}


# ============================================================ integrations & ingest
@mock("list_integrations")
def m_list_integrations(request: Request, **_: Any) -> Any:
    return store().d["integrations"]["integrations"]


@mock("connect_integration")
def m_connect(request: Request, provider: str, **_: Any) -> Any:
    return {"authorize_url": f"https://auth.example.test/{provider}/authorize?state=mock-state"}


@mock("oauth_callback")
def m_oauth_cb(request: Request, provider: str, code: str, state: str, **_: Any) -> Any:
    return RedirectResponse(
        f"{get_settings().web_url}/settings/integrations?connected={provider}", status_code=302
    )


@mock("list_hubspot_properties")
def m_props(request: Request, **_: Any) -> Any:
    return store().d["integrations"]["hubspot_properties"]


@mock("list_slack_users")
def m_slack_users(request: Request, **_: Any) -> Any:
    return store().d["integrations"]["slack_users"]


def _integration(integration_id: Any) -> dict[str, Any]:
    i = next(
        (x for x in store().d["integrations"]["integrations"] if x["id"] == str(integration_id)),
        None,
    )
    if i is None:
        raise not_found("Integration")
    return i


@mock("trigger_sync")
def m_sync(request: Request, integration_id: Any, **_: Any) -> Any:
    i = _integration(integration_id)
    if i["status"] == "needs_reauth":
        raise AppError("integration_needs_reauth")
    return {"sync_run_id": str(uuid4()), "status": "running"}


@mock("disconnect_integration")
def m_disconnect(request: Request, integration_id: Any, **_: Any) -> Any:
    _integration(integration_id)["status"] = "disconnected"
    return {"ok": True, "detail": {}}


@mock("list_sync_runs")
def m_sync_runs(request: Request, integration_id: Any, **_: Any) -> Any:
    _integration(integration_id)
    return store().d["integrations"]["sync_runs"]


@mock("get_field_mapping")
def m_get_mapping(request: Request, **_: Any) -> Any:
    return store().d["integrations"]["field_mapping"]


@mock("put_field_mapping")
def m_put_mapping(request: Request, body: Any, **_: Any) -> Any:
    fm = store().d["integrations"]["field_mapping"]
    fm.update(body.model_dump())
    fm["updated_at"] = now()
    return fm


@mock("ingest_usage")
def m_ingest(request: Request, rows: list[Any], **_: Any) -> Any:
    if not request.headers.get("authorization", "").startswith("Bearer rk_"):
        raise AppError("unauthenticated", "Provide an API key as 'Bearer rk_live_...'")
    if len(rows) > 1000:
        raise AppError("validation_error", "Maximum 1,000 rows per batch")
    rejected = [
        {"index": i, "reason": "unknown account"}
        for i, r in enumerate(rows)
        if r.account_key == "unknown.test"
    ]
    return {"accepted": len(rows) - len(rejected), "rejected": rejected}


@mock("upload_usage_csv")
def m_csv(request: Request, file: Any, mapping: str, **_: Any) -> Any:
    try:
        json.loads(mapping)
    except ValueError as e:
        raise AppError("validation_error", "`mapping` must be valid JSON") from e
    return {
        "job_id": str(uuid4()),
        "status": "queued",
        "progress": 0.0,
        "accepted": 0,
        "errors": [],
    }


@mock("get_usage_csv_job")
def m_csv_job(request: Request, job_id: Any, **_: Any) -> Any:
    return {"job_id": str(job_id), "status": "done", "progress": 1.0, "accepted": 118,
            "errors": [{"index": 4, "reason": "unknown account"}]}  # fmt: skip


# ============================================================ today / accounts
def _account(account_id: Any) -> dict[str, Any]:
    a = next((x for x in store().d["accounts"]["list"] if x["id"] == str(account_id)), None)
    if a is None:
        raise not_found("Account")
    return a


def _cards_for(finding_id: str) -> list[dict[str, Any]]:
    return [c for c in store().d["cards"] if c["finding_id"] == finding_id]


def _card_ref(c: dict[str, Any]) -> dict[str, Any]:
    return {k: c[k] for k in ("id", "type", "tier", "status", "title")}


@mock("get_today")
async def m_today(request: Request, type: str = "all", owner: str = "me", **_: Any) -> Any:
    a = await actor(request)
    s = store().d
    items = []
    for f in s["findings"]:
        if f["status"] != "open" or (type != "all" and f["type"] != type):
            continue
        acc = _account(f["account_id"])
        if owner == "me" and is_demo_user(a["id"]) and acc["owner"]["id"] != a["id"]:
            continue
        if owner not in ("me", "all") and acc["owner"]["id"] != owner:
            continue
        pending = sum(1 for c in _cards_for(f["id"]) if c["status"] == "pending_approval")
        items.append({
            "finding_id": f["id"], "type": f["type"], "severity": f["severity"], "priority_score": f["priority_score"],
            "title": f["title"], "summary": f["summary"],
            "account": {k: acc[k] for k in ("id", "name", "arr", "renewal_date", "renewal_in_days", "owner", "crm_health")},
            "top_reasons": f["claims"][:2], "pending_cards": pending,
            "unknowns_count": len(f["unknowns"]), "contradictions_count": len(f["contradictions"]),
            "is_new": f["first_seen_at"] > D.ts(days_ago=1.5), "changed_since_yesterday": f["last_seen_at"] > D.ts(hours_ago=24),
        })  # fmt: skip
    items.sort(key=lambda i: -i["priority_score"])
    return {
        "generated_at": now(), "items": items,
        "counts": {"risk": sum(i["type"] == "risk" for i in items), "expansion": sum(i["type"] == "expansion" for i in items),
                   "pending_cards": sum(i["pending_cards"] for i in items)},
    }  # fmt: skip


@mock("list_accounts")
def m_accounts(request: Request, page: PageParams, query: str | None = None, owner: str | None = None,
               risk: str | None = None, renewal_within: int | None = None, sort: str = "priority", **_: Any) -> Any:  # fmt: skip
    items = list(store().d["accounts"]["list"])
    if query:
        items = [
            a
            for a in items
            if query.lower() in a["name"].lower() or any(query.lower() in d for d in a["domains"])
        ]
    if owner and owner != "all":
        items = [a for a in items if a["owner"]["id"] == owner]
    if risk:
        items = [a for a in items if a["risk_level"] == risk]
    if renewal_within:
        items = [
            a
            for a in items
            if a["renewal_in_days"] is not None and a["renewal_in_days"] <= renewal_within
        ]
    keys: dict[str, Callable[[dict[str, Any]], Any]] = {
        "priority": lambda a: -(a["priority_score"] or 0),
        "arr": lambda a: -(a["arr"] or 0),
        "renewal": lambda a: a["renewal_in_days"] or 10**6,
        "name": lambda a: a["name"].lower(),
    }
    items.sort(key=keys[sort])
    return page_of(items, page)


@mock("get_account")
def m_account(request: Request, account_id: Any, **_: Any) -> Any:
    a = _account(account_id)
    fs = [
        f
        for f in store().d["findings"]
        if f["account_id"] == a["id"] and f["status"] in ("open", "needs_review", "in_review")
    ]
    key = next(k for k, v in D.ACC.items() if v == a["id"])
    return {**a,
            "metrics": {"active_users": 32 if key == "acme" else 40, "active_users_change_pct": -38.5 if key == "acme" else 0.0,
                        "seats_used": 96 if key == "globex" else None, "days_since_last_meeting": 21 if key == "acme" else 8,
                        "unanswered_emails": 2 if key == "acme" else 0, "open_deals": 1},
            "open_findings": [{k: f[k] for k in ("id", "type", "severity", "title", "priority_score")} for f in fs],
            "data_gaps": ["No product usage data connected"] if key == "soylent" else []}  # fmt: skip


@mock("get_account_timeline")
def m_timeline(
    request: Request, account_id: Any, page: PageParams, types: str | None = None, **_: Any
) -> Any:
    key = next((k for k, v in D.ACC.items() if v == str(account_id)), None)
    if key is None:
        raise not_found("Account")
    items = store().d["accounts"]["timeline"][key]
    if types:
        wanted = set(types.split(","))
        items = [e for e in items if e["type"] in wanted]
    return page_of(sorted(items, key=lambda e: e["occurred_at"], reverse=True), page)


@mock("get_account_usage")
def m_usage(
    request: Request, account_id: Any, granularity: str = "week", weeks: int = 12, **_: Any
) -> Any:
    key = next((k for k, v in D.ACC.items() if v == str(account_id)), None)
    if key is None:
        raise not_found("Account")
    series = copy.deepcopy(store().d["accounts"]["usage"][key])
    series["points"] = series["points"][-weeks:]
    return series


def _by_account(opid_key: str, account_id: Any) -> Any:
    key = next((k for k, v in D.ACC.items() if v == str(account_id)), None)
    if key is None:
        raise not_found("Account")
    return store().d["accounts"][opid_key][key]


@mock("list_account_contacts")
def m_contacts(request: Request, account_id: Any, **_: Any) -> Any:
    return _by_account("contacts", account_id)


@mock("list_account_deals")
def m_deals(request: Request, account_id: Any, **_: Any) -> Any:
    return _by_account("deals", account_id)


@mock("run_account")
def m_run(request: Request, account_id: Any, **_: Any) -> Any:
    _account(account_id)
    return {"agent_run_id": str(uuid4())}


@mock("patch_account")
def m_patch_account(request: Request, account_id: Any, body: Any, **_: Any) -> Any:
    a = _account(account_id)
    if body.status:
        a["status"] = body.status
    for d in body.add_domains or []:
        if d.lower() not in a["domains"]:
            a["domains"].append(d.lower())
    return m_account(request, account_id)


# ============================================================ findings
def _finding(finding_id: Any) -> dict[str, Any]:
    f = next((x for x in store().d["findings"] if x["id"] == str(finding_id)), None)
    if f is None:
        raise not_found("Finding")
    return f


def _finding_out(f: dict[str, Any]) -> dict[str, Any]:
    return {**f, "cards": [_card_ref(c) for c in _cards_for(f["id"])]}


@mock("list_findings")
def m_findings(request: Request, page: PageParams, status: str | None = None, type: str | None = None,
               severity: str | None = None, account_id: Any = None, **_: Any) -> Any:  # fmt: skip
    items = [f for f in store().d["findings"]
             if (not status or f["status"] == status) and (not type or f["type"] == type)
             and (not severity or f["severity"] == severity) and (not account_id or f["account_id"] == str(account_id))]  # fmt: skip
    items.sort(key=lambda f: -f["priority_score"])
    return page_of(items, page)


@mock("get_finding")
def m_finding(request: Request, finding_id: Any, **_: Any) -> Any:
    return _finding_out(_finding(finding_id))


@mock("dismiss_finding")
async def m_dismiss(request: Request, finding_id: Any, body: Any, **_: Any) -> Any:
    f = _finding(finding_id)
    f.update(status="dismissed", dismissed_reason=body.reason)
    f["history"].append({"ts": now(), "event": "finding.dismissed"})
    log_event(
        "finding.dismissed",
        "finding",
        f["id"],
        f["account_id"],
        (await actor(request))["id"],
        f"Dismissed: {body.reason}",
    )
    return _finding_out(f)


@mock("snooze_finding")
async def m_snooze(request: Request, finding_id: Any, body: Any, **_: Any) -> Any:
    f = _finding(finding_id)
    f.update(status="snoozed", snoozed_until=body.until.isoformat())
    f["history"].append({"ts": now(), "event": "finding.snoozed"})
    log_event(
        "finding.snoozed",
        "finding",
        f["id"],
        f["account_id"],
        (await actor(request))["id"],
        "Snoozed",
    )
    return _finding_out(f)


@mock("reopen_finding")
def m_reopen(request: Request, finding_id: Any, **_: Any) -> Any:
    f = _finding(finding_id)
    if f["status"] not in ("dismissed", "snoozed"):
        raise AppError("conflict", "Only dismissed or snoozed findings can be reopened")
    f.update(status="open", dismissed_reason=None, snoozed_until=None)
    f["history"].append({"ts": now(), "event": "finding.updated"})
    return _finding_out(f)


@mock("finding_feedback")
def m_feedback(request: Request, finding_id: Any, body: Any, **_: Any) -> Any:
    _finding(finding_id)
    return {"ok": True, "detail": {}}


# ============================================================ cards
def _card(card_id: Any) -> dict[str, Any]:
    c = next((x for x in store().d["cards"] if x["id"] == str(card_id)), None)
    if c is None:
        raise not_found("Action card")
    return c


def _validate_payload(card: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return ACTION_PAYLOADS[card["type"]].model_validate(payload).model_dump(mode="json")
    except ValidationError as e:
        errors = [{"loc": list(x["loc"]), "msg": x["msg"]} for x in e.errors()]
        raise AppError("validation_error", details={"errors": errors}) from e


def _require_status(card: dict[str, Any], *allowed: str) -> None:
    if card["status"] not in allowed:
        raise AppError("card_not_pending", f"Card is {card['status']}, not {' or '.join(allowed)}", details={"status": card["status"]})  # fmt: skip


@mock("list_cards")
async def m_cards(request: Request, page: PageParams, status: str | None = None, assignee: str | None = None,
                  type: str | None = None, **_: Any) -> Any:  # fmt: skip
    a = await actor(request)
    items = [
        c
        for c in store().d["cards"]
        if (not status or c["status"] == status) and (not type or c["type"] == type)
    ]
    if assignee == "me" and is_demo_user(a["id"]):
        items = [c for c in items if c["assignee_user_id"] == a["id"]]
    elif assignee and assignee != "me":
        items = [c for c in items if c["assignee_user_id"] == assignee]
    return page_of(items, page)


@mock("get_card")
def m_card(request: Request, card_id: Any, **_: Any) -> Any:
    return _card(card_id)


@mock("patch_card")
def m_patch_card(request: Request, card_id: Any, body: Any, **_: Any) -> Any:
    c = _card(card_id)
    _require_status(c, "proposed", "pending_approval")
    c["edited_payload"] = _validate_payload(c, body.edited_payload)
    return c


@mock("approve_card")
async def m_approve(request: Request, card_id: Any, body: Any, **_: Any) -> Any:
    c = _card(card_id)
    if c["tier"] == 3 or c["status"] == "blocked":
        raise AppError("tier_blocked")
    _require_status(c, "pending_approval")
    if body.edited_payload is not None:
        c["edited_payload"] = _validate_payload(c, body.edited_payload)
    a = await actor(request)
    c.update(status="approved", decided_by=a["id"], decided_at=now(), decision_channel="web")
    log_event(
        "card.approved", "action_card", c["id"], c["account_id"], a["id"], f"Approved: {c['title']}"
    )
    return c


@mock("reject_card")
async def m_reject(request: Request, card_id: Any, body: Any, **_: Any) -> Any:
    c = _card(card_id)
    _require_status(c, "pending_approval")
    a = await actor(request)
    c.update(status="rejected", decided_by=a["id"], decided_at=now(), decision_channel="web",
             rejection_reason=body.reason, rejection_note=body.note)  # fmt: skip
    log_event(
        "card.rejected",
        "action_card",
        c["id"],
        c["account_id"],
        a["id"],
        f"Rejected: {body.reason}",
    )
    return c


@mock("assign_card")
def m_assign(request: Request, card_id: Any, body: Any, **_: Any) -> Any:
    c = _card(card_id)
    _require_status(c, "proposed", "pending_approval")
    if not any(m["user_id"] == str(body.user_id) for m in store().d["members"]["members"]):
        raise not_found("Member")
    c["assignee_user_id"] = str(body.user_id)
    return c


@mock("revert_card")
async def m_revert(request: Request, card_id: Any, **_: Any) -> Any:
    c = _card(card_id)
    if c["status"] != "executed":
        raise AppError(
            "card_invalid_state", f"Only executed cards can be reverted (is {c['status']})"
        )
    if c["type"] == "crm_field_update" and request.headers.get("x-mock-revert-conflict"):
        raise AppError(
            "revert_conflict",
            details={"field": "health_status", "current": "Red", "ours": "At Risk"},
        )
    a = await actor(request)
    c.update(status="reverted", reverted_at=now())
    log_event(
        "card.reverted", "action_card", c["id"], c["account_id"], a["id"], f"Reverted: {c['title']}"
    )
    return c


@mock("retry_card")
async def m_retry(request: Request, card_id: Any, **_: Any) -> Any:
    c = _card(card_id)
    if c["status"] != "failed":
        raise AppError("card_invalid_state", f"Only failed cards can be retried (is {c['status']})")
    c.update(status="approved", error=None)
    return c


# ============================================================ decision log
@mock("list_log")
def m_log(request: Request, page: PageParams, account_id: str | None = None, event: str | None = None,
          actor: str | None = None, **_: Any) -> Any:  # fmt: skip
    items = [e for e in store().d["log"]
             if (not account_id or e["account_id"] == account_id) and (not event or e["event"] == event)
             and (not actor or e["actor_id"] == actor)]  # fmt: skip
    return page_of(sorted(items, key=lambda e: -e["id"]), page)


@mock("verify_log")
def m_verify(request: Request, **_: Any) -> Any:
    return {"ok": True, "checked": len(store().d["log"]), "first_bad_id": None}


@mock("get_log_entry")
def m_log_entry(request: Request, entry_id: int, **_: Any) -> Any:
    s = store().d
    e = next((x for x in s["log"] if x["id"] == entry_id), None)
    if e is None:
        raise not_found("Log entry")
    related = [x for x in s["log"] if x["entity_id"] == e["entity_id"] and x["id"] != e["id"]]
    detail: dict[str, Any] = {"entry": e, "data": {}, "related": sorted(related, key=lambda x: x["id"]),
                              "evidence_snapshot": [], "rule_metrics": [], "payload_diff": [], "executions": []}  # fmt: skip
    if e["entity_type"] == "finding":
        f = next((x for x in s["findings"] if x["id"] == e["entity_id"]), None)
        if f:
            detail["evidence_snapshot"] = f["evidence"]
            detail["rule_metrics"] = f["rule_hits"]
            detail["data"] = {
                "model": f["model"],
                "prompt_version": f["prompt_version"],
                "claims": f["claims"],
            }
    if e["entity_type"] == "action_card":
        c = next((x for x in s["cards"] if x["id"] == e["entity_id"]), None)
        if c:
            if c["edited_payload"]:
                detail["payload_diff"] = [{"field": k, "proposed": str(c["payload"].get(k)), "edited": str(v)}
                                          for k, v in c["edited_payload"].items() if c["payload"].get(k) != v]  # fmt: skip
            if c["status"] in ("executed", "reverted", "failed"):
                detail["executions"] = [{"attempt": 1, "status": "failed" if c["status"] == "failed" else "succeeded",
                                         "started_at": c["created_at"], "finished_at": c["created_at"], "error": c["error"]}]  # fmt: skip
    return detail


@mock("export_log")
def m_export(request: Request, body: Any, **_: Any) -> Any:
    job = {
        "job_id": str(uuid4()),
        "status": "done",
        "download_url": f"https://files.example.test/exports/log.{body.format}?sig=mock",
    }
    store().flags_state[f"export:{job['job_id']}"] = job
    return job


@mock("get_log_export")
def m_get_export(request: Request, job_id: str, **_: Any) -> Any:
    job = store().flags_state.get(f"export:{job_id}")
    if job is None:
        raise not_found("Export job")
    return job


# ============================================================ runs, rules, autonomy, reviews
@mock("list_runs")
def m_runs(
    request: Request, page: PageParams, account_id: Any = None, status: str | None = None, **_: Any
) -> Any:
    items = [r for r in store().d["ops"]["runs"] if (not account_id or r["account_id"] == str(account_id)) and (not status or r["status"] == status)]  # fmt: skip
    return page_of(items, page)


@mock("get_run")
def m_run_detail(request: Request, run_id: Any, **_: Any) -> Any:
    r = next((x for x in store().d["ops"]["runs"] if x["id"] == str(run_id)), None)
    if r is None:
        raise not_found("Run")
    steps = [{"name": n, "status": "ok", "duration_ms": 120 + i * 40, "detail": None} for i, n in enumerate(["load_context", "rules", "explain", "plan_actions", "policy"])]  # fmt: skip
    return {**r, "steps": steps, "prompt_versions": {"explain": "template@1"}, "trace_url": None}


@mock("list_rules")
def m_rules(request: Request, **_: Any) -> Any:
    return store().d["ops"]["rules"]


def _rule(key: str) -> dict[str, Any]:
    r = next((x for x in store().d["ops"]["rules"] if x["key"] == key), None)
    if r is None:
        raise not_found("Rule")
    return r


@mock("put_rule")
def m_put_rule(request: Request, key: str, body: Any, **_: Any) -> Any:
    r = _rule(key)
    unknown = set(body.params) - set(r["default_params"])
    if unknown:
        raise AppError("validation_error", details={"unknown_params": sorted(unknown)})
    r.update(enabled=body.enabled, params={**r["default_params"], **body.params}, updated_at=now())
    return r


@mock("preview_rule")
def m_preview_rule(request: Request, key: str, body: Any, **_: Any) -> Any:
    _rule(key)
    return {
        "would_fire": 2,
        "currently_firing": 1,
        "sample_account_ids": [D.ACC["acme"], D.ACC["initech"]],
    }


@mock("list_autonomy")
def m_autonomy(request: Request, **_: Any) -> Any:
    return store().d["ops"]["autonomy"]


@mock("put_autonomy")
def m_put_autonomy(request: Request, action_type: str, body: Any, **_: Any) -> Any:
    p = next((x for x in store().d["ops"]["autonomy"] if x["action_type"] == action_type), None)
    if p is None:
        raise not_found("Policy")
    if p["locked"] and body.tier < p["tier"]:
        raise AppError("tier_blocked", "This tier is locked and cannot be lowered")
    p.update(tier=body.tier, conditions=body.conditions, updated_at=now())
    return p


@mock("list_entity_reviews")
def m_reviews(request: Request, page: PageParams, **_: Any) -> Any:
    return page_of(store().d["ops"]["entity_reviews"], page)


@mock("resolve_entity_review")
def m_resolve(request: Request, review_id: Any, body: Any, **_: Any) -> Any:
    r = next((x for x in store().d["ops"]["entity_reviews"] if x["id"] == str(review_id)), None)
    if r is None:
        raise not_found("Review")
    if not body.ignore and body.account_id is None:
        raise AppError("validation_error", "Provide account_id or ignore=true")
    r["status"] = "ignored" if body.ignore else "resolved"
    return {"ok": True, "detail": {}}


# ============================================================ notifications & stream
@mock("list_notifications")
def m_notifications(request: Request, page: PageParams, unread: bool = False, **_: Any) -> Any:
    items = [n for n in store().d["notifications"] if not unread or n["read_at"] is None]
    return page_of(items, page)


@mock("mark_notifications_read")
def m_read(request: Request, body: Any, **_: Any) -> Any:
    ids = {str(i) for i in body.ids or []}
    for n in store().d["notifications"]:
        if (body.all or n["id"] in ids) and n["read_at"] is None:
            n["read_at"] = now()
    return {"ok": True, "detail": {}}


@mock("stream")
async def m_stream(request: Request, **_: Any) -> Any:
    once = request.headers.get("x-mock-stream-once") == "1"

    async def gen() -> AsyncIterator[str]:
        yield "retry: 3000\n\n"
        yield f"event: notification.created\ndata: {json.dumps({'type': 'notification.created', 'id': D.uid('notif:0'), 'ts': now(), 'data': {'kind': 'finding_high'}})}\n\n"
        if once:
            return
        while True:
            await asyncio.sleep(20)
            yield ": heartbeat\n\n"

    return StreamingResponse(
        gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


# ============================================================ slack
@mock("slack_events")
def m_slack_events(request: Request, payload: dict[str, Any], **_: Any) -> Any:
    if payload.get("type") == "url_verification":
        return {"ok": True, "challenge": payload.get("challenge"), "extra": {}}
    return {"ok": True, "challenge": None, "extra": {}}


@mock("slack_interactions")
def m_slack_interactions(request: Request, payload: dict[str, Any], **_: Any) -> Any:
    return {"ok": True, "challenge": None, "extra": {}}


@mock("slack_oauth_callback")
def m_slack_cb(request: Request, code: str, state: str, **_: Any) -> Any:
    return RedirectResponse(
        f"{get_settings().web_url}/settings/integrations?connected=slack", status_code=302
    )


# ============================================================ admin
def _admin_org(org_id: Any) -> dict[str, Any]:
    o = next((x for x in store().d["admin"]["orgs"] if x["id"] == str(org_id)), None)
    if o is None:
        raise not_found("Organization")
    return o


@mock("list_admin_orgs")
def m_admin_orgs(request: Request, page: PageParams, **_: Any) -> Any:
    return page_of(store().d["admin"]["orgs"], page)


@mock("get_admin_org")
def m_admin_org(request: Request, org_id: Any, **_: Any) -> Any:
    return {**_admin_org(org_id), "integrations": [{"provider": i["provider"], "status": i["status"]} for i in store().d["integrations"]["integrations"]],
            "recent_errors": ["usage_api: last batch had 12 rejected rows"]}  # fmt: skip


@mock("suspend_org")
def m_suspend(request: Request, org_id: Any, **_: Any) -> Any:
    o = _admin_org(org_id)
    o["status"] = "suspended"
    return o


@mock("unsuspend_org")
def m_unsuspend(request: Request, org_id: Any, **_: Any) -> Any:
    o = _admin_org(org_id)
    o["status"] = "active"
    return o


@mock("list_admin_jobs")
def m_jobs(request: Request, page: PageParams, **_: Any) -> Any:
    return page_of(store().d["admin"]["jobs"], page)


def _job(job_id: Any) -> dict[str, Any]:
    j = next((x for x in store().d["admin"]["jobs"] if x["id"] == str(job_id)), None)
    if j is None:
        raise not_found("Job")
    return j


@mock("retry_admin_job")
def m_retry_job(request: Request, job_id: Any, **_: Any) -> Any:
    _job(job_id)["retried_at"] = now()
    return {"ok": True, "detail": {}}


@mock("discard_admin_job")
def m_discard_job(request: Request, job_id: Any, **_: Any) -> Any:
    store().d["admin"]["jobs"].remove(_job(job_id))
    return {"ok": True, "detail": {}}


@mock("llm_health")
def m_llm(request: Request, **_: Any) -> Any:
    return {
        "status": "not_configured",
        "mode": get_settings().ai_mode,
        "latency_ms": None,
        "model": "template",
    }


@mock("list_evals")
def m_evals(request: Request, **_: Any) -> Any:
    return store().d["admin"]["evals"]


@mock("run_evals")
def m_run_evals(request: Request, body: Any, **_: Any) -> Any:
    return {"ok": True, "detail": {"suite": body.suite}}


@mock("list_flags")
def m_flags(request: Request, **_: Any) -> Any:
    return store().d["admin"]["flags"]


@mock("put_flag")
def m_put_flag(request: Request, body: Any, **_: Any) -> Any:
    flags = store().d["admin"]["flags"]
    f = next((x for x in flags if x["key"] == body.key), None)
    if f is None:
        f = {"key": body.key, "default": False, "per_org": {}}
        flags.append(f)
    if body.default is not None:
        f["default"] = body.default
    if body.per_org is not None:
        f["per_org"] = body.per_org
    return f
