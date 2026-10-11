"""Regression tests for security findings H5-H8 of the backend audit."""

import hashlib
import re
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import DEV_INTERNAL_KEY, DEV_JWT_SECRET, Settings, get_settings
from app.main import create_app
from tests.helpers import SeededOrg, bearer, mint_jwt

GOOD = {
    "api_jwt_secret": "x" * 40,
    "internal_api_key": "y" * 24,
    "token_enc_keys": "k1:MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
}


# ------------------------------------------------------------------ H7: unsafe defaults
def test_local_and_test_envs_allow_dev_defaults() -> None:
    for env in ("local", "test"):
        Settings(_env_file=None, app_env=env)  # type: ignore[call-arg]


@pytest.mark.parametrize("env", ["staging", "prod", "production"])
def test_non_local_env_refuses_dev_secrets(env: str) -> None:
    with pytest.raises(ValidationError) as ei:
        Settings(_env_file=None, app_env=env)  # type: ignore[call-arg]
    msg = str(ei.value)
    assert "API_JWT_SECRET" in msg and "INTERNAL_API_KEY" in msg and "TOKEN_ENC_KEYS" in msg


def test_non_local_env_accepts_real_secrets_and_rejects_weak_ones() -> None:
    Settings(_env_file=None, app_env="prod", **GOOD)  # type: ignore[arg-type]
    for bad in (
        {"api_jwt_secret": DEV_JWT_SECRET},
        {"internal_api_key": DEV_INTERNAL_KEY},
        {"api_jwt_secret": "short"},
    ):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, app_env="prod", **{**GOOD, **bad})  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="MOCK_AUTH"):
        Settings(_env_file=None, app_env="staging", mock_api=True, mock_auth=False, **GOOD)  # type: ignore[arg-type]


# ------------------------------------------------------------------ H8: rate limits are wired
async def test_default_rate_limit_applies_per_user_and_returns_429(
    org_a: SeededOrg, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    get_settings.cache_clear()
    app = create_app()
    h = bearer(mint_jwt(org_a.users["owner"], org_a.org_id))
    other = bearer(mint_jwt(org_a.users["admin"], org_a.org_id))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        codes = [(await c.get("/api/v1/me", headers=h)).status_code for _ in range(4)]
        limited = await c.get("/api/v1/me", headers=h)
        other_user = await c.get("/api/v1/me", headers=other)
    get_settings.cache_clear()
    assert codes == [200, 200, 200, 429]
    assert (
        limited.json()["error"]["code"] == "rate_limited"
        and int(limited.headers["retry-after"]) >= 1
    )
    assert other_user.status_code == 200  # buckets are per user


async def test_sensitive_routes_use_the_lower_limit_and_stream_is_exempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    get_settings.cache_clear()
    from app.contract import SENSITIVE_GROUPS, UNLIMITED_GROUPS, build_router

    router = build_router(get_settings())
    get_settings.cache_clear()
    by_id = {r.operation_id: r for r in router.routes if hasattr(r, "operation_id")}  # type: ignore[attr-defined]
    assert len(by_id["ingest_usage"].dependencies) == 2  # rate limit + api key  # type: ignore[attr-defined]
    assert len(by_id["stream"].dependencies) == 1 and "stream" in UNLIMITED_GROUPS  # type: ignore[attr-defined]
    assert {"ingest", "oauth", "api_keys"} <= SENSITIVE_GROUPS


# ------------------------------------------------------------------ H5: ingest authentication
async def _api_key(org: SeededOrg, engine: AsyncEngine, scopes: list[str]) -> str:
    raw = "rk_live_" + uuid4().hex
    async with engine.begin() as c:
        await c.execute(
            text(
                "INSERT INTO api_keys (id, org_id, name, prefix, key_hash, scopes) "
                "VALUES (:i, :o, 'k', 'rk_live_', :h, :s)"
            ),
            {
                "i": uuid4(),
                "o": org.org_id,
                "h": hashlib.sha256(raw.encode()).hexdigest(),
                "s": scopes,
            },
        )
    return raw


ROW = [
    {
        "account_key": "nobody.example.com", "account_key_type": "domain", "period_start": "2026-10-05",
        "granularity": "week", "active_users": 3,
    }
]  # fmt: skip


async def test_ingest_requires_the_ingest_scope(
    client: AsyncClient, org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    good = await _api_key(org_a, owner_engine, ["ingest:usage"])
    bad = await _api_key(org_a, owner_engine, ["something:else"])
    ok = await client.post("/api/v1/ingest/usage", json=ROW, headers=bearer(good))
    assert ok.status_code == 200 and ok.json()["rejected"][0]["reason"] == "unknown_account"
    denied = await client.post("/api/v1/ingest/usage", json=ROW, headers=bearer(bad))
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "forbidden"


async def test_ingest_rejects_user_jwts_even_for_owners_and_unknown_or_revoked_keys(
    client: AsyncClient, org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    for role in ("owner", "viewer"):
        r = await client.post(
            "/api/v1/ingest/usage",
            json=ROW,
            headers=bearer(mint_jwt(org_a.users[role], org_a.org_id)),
        )
        assert r.status_code == 401, role
    assert (
        await client.post("/api/v1/ingest/usage", json=ROW, headers=bearer("rk_live_unknown"))
    ).status_code == 401
    key = await _api_key(org_a, owner_engine, ["ingest:usage"])
    async with owner_engine.begin() as c:
        await c.execute(
            text("UPDATE api_keys SET revoked_at = now() WHERE org_id = :o"), {"o": org_a.org_id}
        )
    assert (
        await client.post("/api/v1/ingest/usage", json=ROW, headers=bearer(key))
    ).status_code == 401


async def test_demo_key_backdoor_is_gone(
    client: AsyncClient, org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    token = "rk_live_" + uuid4().hex
    async with owner_engine.begin() as c:  # the old fallback hashed "demo-<token>"
        await c.execute(
            text(
                "INSERT INTO api_keys (id, org_id, name, prefix, key_hash, scopes) VALUES (:i, :o, 'k', 'rk_live_', :h, ARRAY['ingest:usage'])"
            ),
            {
                "i": uuid4(),
                "o": org_a.org_id,
                "h": hashlib.sha256(f"demo-{token}".encode()).hexdigest(),
            },
        )
    assert (
        await client.post("/api/v1/ingest/usage", json=ROW, headers=bearer(token))
    ).status_code == 401


# ------------------------------------------------------------------ H6: BYPASSRLS call sites are contained
# `admin_session()` bypasses RLS. It is allowed ONLY where there is no tenant yet (login/invite/
# key/webhook resolution), for platform fan-out jobs, and in /admin. Adding a new call site must be
# a conscious decision: extend this list in the same PR and justify it in docs/conventions.md.
ADMIN_SESSION_ALLOWED = {
    "app/auth/deps.py": "membership lookup across orgs, superadmin check (no tenant context yet)",
    "app/services/auth.py": "email+password sign-in/sign-up: users are global, no tenant yet",
    "app/services/api_keys.py": "API key -> org resolution (the key IS the tenant identity)",
    "app/services/invites.py": "invite acceptance by a user who is not yet a member",
    "app/services/identity.py": "cross-org memberships for /me",
    "app/services/slack.py": "Slack team -> org resolution for signed webhooks",
    "app/services/admin.py": "superadmin /admin routers",
    "app/connectors/google/writes.py": "global feature-flag lookup (flags table has no RLS)",
    "app/workers/celery_app.py": "failed_jobs dead letter (global table)",
    "app/workers/tasks_maintenance.py": "platform fan-out over active/deleted orgs",
    "app/workers/tasks_run.py": "platform fan-out over active orgs",
    "app/workers/tasks_ai.py": "platform fan-out: orgs with unread events (ids only, no content)",
    "app/workers/tasks_slack.py": "platform fan-out for digests",
    "app/workers/tasks_sync.py": "platform fan-out over integrations",
}


def test_admin_session_is_only_used_where_allowed() -> None:
    root = Path(__file__).resolve().parents[1]
    users = {
        str(p.relative_to(root)).replace("\\", "/")
        for p in (root / "app").rglob("*.py")
        if re.search(r"admin_session\(\)", p.read_text(encoding="utf-8")) and p.name != "session.py"
    }
    unexpected = users - set(ADMIN_SESSION_ALLOWED)
    assert not unexpected, f"new BYPASSRLS call sites need review: {sorted(unexpected)}"
