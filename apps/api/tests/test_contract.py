"""Contract + mock-mode tests: every endpoint in backenddeveloper.md section 5.3 exists in the
OpenAPI document and is served by mock mode with a response that validates against its model."""

import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient  # noqa: F401
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import get_settings
from app.contract import ENDPOINTS, REAL_HANDLERS, V1
from app.main import create_app
from app.mocks import data as D
from app.mocks.handlers import reset_store
from app.schemas.action_payloads import ACTION_PAYLOADS
from tests.helpers import SeededOrg, bearer, mint_jwt

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))

# Independent restatement of backenddeveloper.md section 5.3 (+ handover endpoint list).
REQUIRED = [
    ("GET", "/me"), ("PATCH", "/me"), ("POST", "/orgs"), ("GET", "/orgs/current"),
    ("PATCH", "/orgs/current"), ("DELETE", "/orgs/current"), ("GET", "/orgs/current/onboarding"),
    ("GET", "/members"), ("PATCH", "/members/{member_id}"), ("DELETE", "/members/{member_id}"),
    ("POST", "/invites"), ("GET", "/invites"), ("DELETE", "/invites/{invite_id}"), ("POST", "/invites/accept"),
    ("GET", "/integrations"), ("POST", "/integrations/{provider}/connect"),
    ("GET", "/oauth/{provider}/callback"), ("POST", "/integrations/{integration_id}/sync"),
    ("DELETE", "/integrations/{integration_id}"), ("GET", "/integrations/{integration_id}/sync-runs"),
    ("GET", "/integrations/hubspot/properties"), ("GET", "/field-mapping"), ("PUT", "/field-mapping"),
    ("GET", "/integrations/slack/users"),
    ("POST", "/ingest/usage"), ("POST", "/ingest/usage/csv"), ("GET", "/ingest/usage/csv/{job_id}"),
    ("GET", "/api-keys"), ("POST", "/api-keys"), ("DELETE", "/api-keys/{key_id}"),
    ("GET", "/today"), ("GET", "/accounts"), ("GET", "/accounts/{account_id}"),
    ("GET", "/accounts/{account_id}/timeline"), ("GET", "/accounts/{account_id}/usage"),
    ("GET", "/accounts/{account_id}/contacts"), ("GET", "/accounts/{account_id}/deals"),
    ("POST", "/accounts/{account_id}/run"), ("PATCH", "/accounts/{account_id}"),
    ("GET", "/findings"), ("GET", "/findings/{finding_id}"), ("POST", "/findings/{finding_id}/dismiss"),
    ("POST", "/findings/{finding_id}/snooze"), ("POST", "/findings/{finding_id}/reopen"),
    ("POST", "/findings/{finding_id}/feedback"),
    ("GET", "/action-cards"), ("GET", "/action-cards/{card_id}"), ("PATCH", "/action-cards/{card_id}"),
    ("POST", "/action-cards/{card_id}/approve"), ("POST", "/action-cards/{card_id}/reject"),
    ("POST", "/action-cards/{card_id}/assign"), ("POST", "/action-cards/{card_id}/revert"),
    ("POST", "/action-cards/{card_id}/retry"),
    ("GET", "/log"), ("GET", "/log/{entry_id}"), ("GET", "/log/verify"), ("POST", "/log/export"),
    ("GET", "/runs"), ("GET", "/runs/{run_id}"), ("GET", "/rules"), ("PUT", "/rules/{key}"),
    ("POST", "/rules/{key}/preview"), ("GET", "/autonomy"), ("PUT", "/autonomy/{action_type}"),
    ("GET", "/entity-reviews"), ("POST", "/entity-reviews/{review_id}/resolve"),
    ("GET", "/notifications"), ("POST", "/notifications/read"), ("GET", "/stream"),
    ("GET", "/admin/orgs"), ("GET", "/admin/orgs/{org_id}"), ("POST", "/admin/orgs/{org_id}/suspend"),
    ("GET", "/admin/jobs"), ("POST", "/admin/jobs/{job_id}/retry"), ("GET", "/admin/llm/health"),
    ("GET", "/admin/evals"), ("POST", "/admin/evals/run"), ("GET", "/admin/flags"), ("PUT", "/admin/flags"),
    ("POST", "/slack/events"), ("POST", "/slack/interactions"),
]  # fmt: skip

PATH_VALUES: dict[str, Any] = {
    "account_id": D.ACC["acme"], "finding_id": D.FINDING_IDS["acme"], "card_id": D.CARD_IDS["acme_email"],
    "member_id": D.uid("membership:member"), "invite_id": D.uid("invite:1"), "key_id": D.uid("key:1"),
    "integration_id": D.uid("integration:hubspot"), "provider": "hubspot", "job_id": D.uid("job:1"),
    "org_id": D.ORG_ID, "entry_id": 4, "run_id": D.uid("run:0"), "key": "R01_usage_drop",
    "action_type": "email_draft", "review_id": D.uid("review:1"),
}  # fmt: skip

BODIES: dict[str, Any] = {
    "patch_me": {"name": "Priya M"}, "create_org": {"name": "New Co"},
    "patch_current_org": {"name": "Demo SaaS Inc"}, "delete_current_org": {"confirm": "Demo SaaS"},
    "patch_member": {"role": "manager"}, "create_invite": {"email": "x@demo-saas.example.com", "role": "member"},
    "accept_invite": {"token": "t"}, "put_field_mapping": {"arr_property": "annualrevenue"},
    "ingest_usage": [{"account_key": "acme.example.com", "account_key_type": "domain", "period_start": "2026-10-01", "granularity": "week", "active_users": 30}],
    "create_api_key": {"name": "k"}, "patch_account": {"add_domains": ["acme.io"]},
    "dismiss_finding": {"reason": "not_relevant"}, "snooze_finding": {"until": "2026-11-01T00:00:00Z"},
    "finding_feedback": {"useful": True}, "patch_card": {"edited_payload": D.EMAIL},
    "approve_card": {}, "reject_card": {"reason": "not_now"}, "assign_card": {"user_id": D.USER_IDS["manager"]},
    "export_log": {"format": "csv"}, "put_rule": {"enabled": True, "params": {"drop_pct": 25}},
    "preview_rule": {"params": {"drop_pct": 20}}, "put_autonomy": {"tier": 2},
    "resolve_entity_review": {"ignore": True}, "mark_notifications_read": {"all": True},
    "run_evals": {"suite": "smoke"}, "put_flag": {"key": "email_send", "default": True},
    "slack_events": {"type": "url_verification", "challenge": "abc"}, "slack_interactions": {"type": "block_actions"},
}  # fmt: skip
PATH_OVERRIDES: dict[str, dict[str, Any]] = {
    "revert_card": {"card_id": D.CARD_IDS["acme_task"]},
    "retry_card": {"card_id": D.CARD_IDS["initech_failed"]},
    "reopen_finding": {"finding_id": D.FINDING_IDS["initech_old"]},
}
QUERIES: dict[str, dict[str, str]] = {
    "oauth_callback": {"code": "c", "state": "s"}, "slack_oauth_callback": {"code": "c", "state": "s"},
}  # fmt: skip


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("MOCK_API", "true")
    get_settings.cache_clear()
    reset_store()
    yield
    get_settings.cache_clear()
    reset_store()


@pytest_asyncio.fixture
async def superadmin(seeded: SeededOrg, owner_engine: AsyncEngine) -> SeededOrg:
    async with owner_engine.begin() as c:
        await c.execute(
            text("UPDATE users SET is_superadmin = true WHERE id = :u"),
            {"u": seeded.users["owner"]},
        )
    return seeded


def _client(app: Any) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


def auth(seeded: SeededOrg, role: str = "owner") -> dict[str, str]:
    return bearer(mint_jwt(seeded.users[role], seeded.org_id))


# --------------------------------------------------------------------- contract
def test_every_documented_endpoint_is_declared() -> None:
    import app.routes  # noqa: F401

    declared = {(d.spec.method, d.spec.path) for d in ENDPOINTS}
    missing = [(m, p) for m, p in REQUIRED if (m, V1 + p) not in declared]
    assert not missing, f"missing from contract: {missing}"


async def test_openapi_has_every_endpoint_with_models_and_page_tags() -> None:
    async with _client(create_app()) as c:
        doc = (await c.get("/openapi.json")).json()
    for method, path in REQUIRED:
        op = doc["paths"].get(V1 + path, {}).get(method.lower())
        assert op, f"{method} {path} missing from OpenAPI"
        assert op["tags"] and op["operationId"]
        ok = [r for code, r in op["responses"].items() if code.startswith(("2", "3"))]
        assert ok, f"{method} {path} has no success response"
    # every JSON 2xx response is a typed schema (no free-form objects)
    for path, ops in doc["paths"].items():
        for method, op in ops.items():
            for code, r in op["responses"].items():
                content = r.get("content", {}).get("application/json")
                if code.startswith("2") and content:
                    assert content["schema"] != {} and content["schema"] != {"type": "object"}, (
                        f"{method} {path}"
                    )
    names = set(doc["components"]["schemas"])
    assert {
        "TodayResponse",
        "FindingDetail",
        "CardOut",
        "CardApproveIn",
    } <= names  # section 5.4 names


def test_internal_openapi_is_separate() -> None:
    from app.internal_app import create_internal_app

    paths = create_internal_app().openapi()["paths"]
    assert len(paths) == 7 and all(p.startswith("/v1/orgs/{org}") for p in paths)


async def test_internal_api_requires_key_and_is_501_until_p6() -> None:
    async with _client(create_app()) as c:
        r = await c.get(f"/internal/v1/orgs/{D.ORG_ID}/events/pending-extraction")
        assert r.status_code == 401
        r = await c.get(
            f"/internal/v1/orgs/{D.ORG_ID}/events/pending-extraction",
            headers={"X-Internal-Key": get_settings().internal_api_key},
        )
        assert r.status_code == 501 and r.json()["error"]["code"] == "not_implemented"
    async with _client(create_app()) as c:
        assert (
            "/v1/orgs/{org}/accounts/{account_id}/context"
            in (await c.get("/internal/openapi.json")).json()["paths"]
        )


def test_non_mock_mode_unimplemented_is_501_and_real_me_stays_real() -> None:
    from app.contract import resolve_mode

    s = get_settings()
    assert resolve_mode("members", "list_members", s) == "501"
    assert resolve_mode("me", "get_me", s) == "real"


# --------------------------------------------------------------------- mock mode
@pytest.mark.parametrize("opid", [d.spec.operation_id for d in ENDPOINTS])
async def test_mock_mode_serves_every_endpoint(
    mock_env: None, superadmin: SeededOrg, opid: str
) -> None:
    d = next(x for x in ENDPOINTS if x.spec.operation_id == opid)
    path = d.spec.path
    for k, v in {**PATH_VALUES, **PATH_OVERRIDES.get(opid, {})}.items():
        path = path.replace("{" + k + "}", str(v))
    headers = {} if d.access == "public" else auth(superadmin)
    kwargs: dict[str, Any] = {"headers": headers, "params": QUERIES.get(opid, {})}
    if opid in BODIES:
        kwargs["json"] = BODIES[opid]
    if opid == "ingest_usage":
        kwargs["headers"] = {"Authorization": "Bearer rk_live_demo"}
    if opid == "upload_usage_csv":
        kwargs.pop("json", None)
        kwargs["files"] = {"file": ("u.csv", b"a,b\n1,2\n", "text/csv")}
        kwargs["data"] = {"mapping": json.dumps({"account_key": "a"})}
    if opid == "stream":
        kwargs["headers"] = {**headers, "X-Mock-Stream-Once": "1"}
    if opid == "get_log_export":
        async with _client(create_app()) as c0:
            job = (
                await c0.post(f"{V1}/log/export", json={"format": "csv"}, headers=headers)
            ).json()
        path = path.replace(D.uid("job:1"), job["job_id"])
    async with _client(create_app()) as c:
        r = await c.request(d.spec.method, path, **kwargs)
    assert r.status_code == d.status_code, (opid, r.status_code, r.text[:300])
    if d.response_class is None:
        assert r.json() is not None


async def test_mock_error_header_returns_registered_error(
    mock_env: None, seeded: SeededOrg
) -> None:
    async with _client(create_app()) as c:
        r = await c.post(
            f"{V1}/action-cards/{D.CARD_IDS['acme_email']}/approve",
            json={},
            headers={**auth(seeded), "X-Mock-Error": "card_not_pending"},
        )
    assert r.status_code == 409 and r.json()["error"]["code"] == "card_not_pending"


async def test_mock_empty_header_returns_empty_lists(mock_env: None, seeded: SeededOrg) -> None:
    async with _client(create_app()) as c:
        for path in ("/action-cards", "/members", "/notifications", "/accounts"):
            r = await c.get(V1 + path, headers={**auth(seeded), "X-Mock-Empty": "true"})
            assert r.json() == {"items": [], "next_cursor": None}, path
        r = await c.get(f"{V1}/today", headers={**auth(seeded), "X-Mock-Empty": "true"})
        assert r.json()["items"] == []


async def test_mock_cards_cover_every_status_and_findings_every_severity(
    mock_env: None, seeded: SeededOrg
) -> None:
    async with _client(create_app()) as c:
        cards = (await c.get(f"{V1}/action-cards?limit=100", headers=auth(seeded))).json()["items"]
        findings = (await c.get(f"{V1}/findings?limit=100", headers=auth(seeded))).json()["items"]
    assert {x["status"] for x in cards} == {
        "proposed", "pending_approval", "approved", "rejected", "executing",
        "executed", "failed", "reverted", "expired", "blocked",
    }  # fmt: skip
    assert {x["severity"] for x in findings} == {"high", "medium", "low"}
    assert {x["type"] for x in findings} == {"risk", "expansion"}
    assert {"open", "dismissed", "needs_review"} <= {x["status"] for x in findings}


async def test_mock_card_state_machine_is_stateful_and_logs(
    mock_env: None, seeded: SeededOrg
) -> None:
    cid = D.CARD_IDS["acme_email"]
    async with _client(create_app()) as c:
        h = auth(seeded)
        r = await c.post(f"{V1}/action-cards/{cid}/approve", json={}, headers=h)
        assert r.status_code == 202 and r.json()["status"] == "approved"
        assert (await c.get(f"{V1}/action-cards/{cid}", headers=h)).json()["status"] == "approved"
        again = await c.post(f"{V1}/action-cards/{cid}/approve", json={}, headers=h)
        assert again.status_code == 409 and again.json()["error"]["code"] == "card_not_pending"
        rej = await c.post(f"{V1}/action-cards/{cid}/reject", json={"reason": "not_now"}, headers=h)
        assert rej.status_code == 409
        # reject another pending card
        r2 = await c.post(
            f"{V1}/action-cards/{D.CARD_IDS['acme_health']}/reject",
            json={"reason": "wrong_action", "note": "n"},
            headers=h,
        )
        assert r2.json()["status"] == "rejected" and r2.json()["rejection_reason"] == "wrong_action"
        events = [e["event"] for e in (await c.get(f"{V1}/log?limit=5", headers=h)).json()["items"]]
        assert events[:2] == ["card.rejected", "card.approved"]
        # finding detail reflects card status
        f = (await c.get(f"{V1}/findings/{D.FINDING_IDS['acme']}", headers=h)).json()
        assert {x["status"] for x in f["cards"]} >= {"approved", "rejected"}
        # today pending count dropped to 0 for acme
        today = (await c.get(f"{V1}/today?owner=all", headers=h)).json()
        acme = next(i for i in today["items"] if i["account"]["name"] == "Acme Corp")
        assert acme["pending_cards"] == 0


async def test_mock_card_edit_validated_and_tier3_blocked_and_revert_rules(
    mock_env: None, seeded: SeededOrg
) -> None:
    async with _client(create_app()) as c:
        h = auth(seeded)
        bad = await c.patch(
            f"{V1}/action-cards/{D.CARD_IDS['acme_email']}",
            json={"edited_payload": {"subject": "x"}},
            headers=h,
        )
        assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"
        ok = await c.patch(
            f"{V1}/action-cards/{D.CARD_IDS['acme_email']}",
            json={"edited_payload": {**D.EMAIL, "subject": "Edited"}},
            headers=h,
        )
        assert ok.json()["edited_payload"]["subject"] == "Edited"
        blocked = await c.post(
            f"{V1}/action-cards/{D.CARD_IDS['acme_blocked']}/approve", json={}, headers=h
        )
        assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "tier_blocked"
        r = await c.post(f"{V1}/action-cards/{D.CARD_IDS['acme_email']}/revert", headers=h)
        assert r.status_code == 409 and r.json()["error"]["code"] == "card_invalid_state"
        ok = await c.post(f"{V1}/action-cards/{D.CARD_IDS['acme_task']}/revert", headers=h)
        assert ok.json()["status"] == "reverted"
        retry = await c.post(f"{V1}/action-cards/{D.CARD_IDS['initech_failed']}/retry", headers=h)
        assert retry.status_code == 202 and retry.json()["status"] == "approved"
        nf = await c.get(f"{V1}/action-cards/{D.uid('nope')}", headers=h)
        assert nf.status_code == 404


async def test_mock_findings_and_notifications_state(mock_env: None, seeded: SeededOrg) -> None:
    async with _client(create_app()) as c:
        h = auth(seeded)
        fid = D.FINDING_IDS["globex"]
        d = await c.post(
            f"{V1}/findings/{fid}/dismiss", json={"reason": "already_handled"}, headers=h
        )
        assert d.json()["status"] == "dismissed"
        assert all(
            i["finding_id"] != fid
            for i in (await c.get(f"{V1}/today?owner=all", headers=h)).json()["items"]
        )
        assert (await c.post(f"{V1}/findings/{fid}/reopen", headers=h)).json()["status"] == "open"
        assert (await c.post(f"{V1}/findings/{fid}/reopen", headers=h)).status_code == 409
        unread = (await c.get(f"{V1}/notifications?unread=true", headers=h)).json()["items"]
        assert len(unread) == 3
        await c.post(f"{V1}/notifications/read", json={"ids": [unread[0]["id"]]}, headers=h)
        assert len((await c.get(f"{V1}/notifications?unread=true", headers=h)).json()["items"]) == 2
        await c.post(f"{V1}/notifications/read", json={"all": True}, headers=h)
        assert (await c.get(f"{V1}/notifications?unread=true", headers=h)).json()["items"] == []


async def test_mock_pagination_cursor(mock_env: None, seeded: SeededOrg) -> None:
    async with _client(create_app()) as c:
        h = auth(seeded)
        first = (await c.get(f"{V1}/action-cards?limit=4", headers=h)).json()
        second = (
            await c.get(f"{V1}/action-cards?limit=4&cursor={first['next_cursor']}", headers=h)
        ).json()
        third = (
            await c.get(f"{V1}/action-cards?limit=4&cursor={second['next_cursor']}", headers=h)
        ).json()
        ids = [x["id"] for p in (first, second, third) for x in p["items"]]
        assert len(ids) == len(set(ids)) == 11 and third["next_cursor"] is None
        bad = await c.get(f"{V1}/action-cards?cursor=garbage", headers=h)
        assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_cursor"


async def test_mock_mode_still_enforces_auth_and_roles(mock_env: None, seeded: SeededOrg) -> None:
    async with _client(create_app()) as c:
        assert (await c.get(f"{V1}/action-cards")).status_code == 401
        v = auth(seeded, "viewer")
        assert (await c.get(f"{V1}/action-cards", headers=v)).status_code == 200
        r = await c.post(
            f"{V1}/action-cards/{D.CARD_IDS['acme_email']}/approve", json={}, headers=v
        )
        assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"
        assert (await c.get(f"{V1}/members", headers=auth(seeded, "member"))).status_code == 200
        assert (
            await c.patch(
                f"{V1}/members/{D.uid('membership:member')}",
                json={"role": "admin"},
                headers=auth(seeded, "member"),
            )
        ).status_code == 403
        assert (await c.get(f"{V1}/admin/orgs", headers=auth(seeded, "admin"))).status_code == 403


async def test_mock_auth_can_be_disabled(mock_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_AUTH", "false")
    get_settings.cache_clear()
    async with _client(create_app()) as c:
        assert (await c.get(f"{V1}/action-cards")).status_code == 200


async def test_real_routers_switches_group_to_real(
    mock_env: None, monkeypatch: pytest.MonkeyPatch, seeded: SeededOrg
) -> None:
    async with _client(create_app()) as c:
        mocked = (await c.get(f"{V1}/me", headers=auth(seeded, "viewer"))).json()
        assert mocked["memberships"][-1]["org_name"] == D.OTHER_ORG_NAME  # mock-only shape
    monkeypatch.setenv("REAL_ROUTERS", "me")
    get_settings.cache_clear()
    async with _client(create_app()) as c:
        real = (await c.get(f"{V1}/me", headers=auth(seeded, "viewer"))).json()
    assert real["role"] == "viewer" and real["org"]["id"] == str(seeded.org_id)
    assert len(real["memberships"]) == 1
    assert "get_me" in REAL_HANDLERS


# --------------------------------------------------------------------- fixtures & docs
def test_mock_json_files_are_up_to_date() -> None:
    from scripts.gen_mocks import TARGET, render

    for name, content in render().items():
        assert (TARGET / name).read_text(encoding="utf-8") == content, (
            f"run scripts/gen_mocks.py ({name})"
        )


def test_endpoints_doc_is_up_to_date() -> None:
    from scripts.gen_endpoints import TARGET, render

    assert TARGET.read_text(encoding="utf-8") == render(), "run scripts/gen_endpoints.py"


def test_fixture_card_payloads_match_their_type_schema() -> None:
    for card in D.CARDS:
        ACTION_PAYLOADS[card["type"]].model_validate(card["payload"])


async def test_stream_mock_emits_sse(mock_env: None, seeded: SeededOrg) -> None:
    async with _client(create_app()) as c:
        r = await c.get(f"{V1}/stream", headers={**auth(seeded), "X-Mock-Stream-Once": "1"})
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "event: notification.created" in r.text
