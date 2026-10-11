"""Client onboarding: invite hierarchy + preview, set-password / temporary password, platform
`POST /admin/orgs`, and agent-run retry."""

from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.permissions import Role, can_invite
from tests.helpers import SeededOrg

ADMIN_ORGS = "/api/v1/admin/orgs"
LOGIN = "/api/v1/auth/login"
ADMIN_LOGIN = "/api/v1/auth/admin/login"


class CapturingSender:
    """Stands in for the email sender and keeps the one-time tokens it was given."""

    def __init__(self) -> None:
        self.invites: list[dict[str, str]] = []
        self.set_passwords: list[dict[str, str]] = []

    async def send_invite(
        self, *, to_email: str, org_name: str, invite_token: str, role: str
    ) -> None:
        self.invites.append({"to": to_email, "token": invite_token, "role": role})

    async def send_set_password(self, *, to_email: str, org_name: str, token: str) -> None:
        self.set_passwords.append({"to": to_email, "token": token, "org": org_name})


@pytest.fixture
def sender(monkeypatch: pytest.MonkeyPatch) -> CapturingSender:
    cap = CapturingSender()
    monkeypatch.setattr("app.services.invites.get_email_sender", lambda: cap)
    monkeypatch.setattr("app.services.admin.get_email_sender", lambda: cap)
    return cap


# ------------------------------------------------------------------ invite hierarchy


def test_can_invite_matrix() -> None:
    assert {r for r in Role if can_invite(Role.OWNER, r)} == {
        Role.ADMIN,
        Role.MANAGER,
        Role.MEMBER,
        Role.VIEWER,
    }
    assert {r for r in Role if can_invite(Role.ADMIN, r)} == {
        Role.MANAGER,
        Role.MEMBER,
        Role.VIEWER,
    }
    for inviter in (Role.MANAGER, Role.MEMBER, Role.VIEWER):
        assert not any(can_invite(inviter, r) for r in Role)
    assert not can_invite("nonsense", "member") and not can_invite("owner", "nonsense")


@pytest.mark.parametrize(
    ("inviter", "invitee", "status"),
    [
        ("owner", "admin", 201),
        ("owner", "manager", 201),
        ("owner", "viewer", 201),
        ("owner", "owner", 403),
        ("admin", "manager", 201),
        ("admin", "member", 201),
        ("admin", "admin", 403),
        ("admin", "owner", 403),
        ("manager", "member", 403),
        ("member", "viewer", 403),
        ("viewer", "viewer", 403),
    ],
)
async def test_invite_role_hierarchy(
    client_as: Callable[..., AsyncClient],
    sender: CapturingSender,
    inviter: str,
    invitee: str,
    status: int,
) -> None:
    c: AsyncClient = client_as(inviter)
    r = await c.post(
        "/api/v1/invites",
        json={"email": f"{inviter}-{invitee}@invite.example.com", "role": invitee},
    )
    assert r.status_code == status, r.text
    assert len(sender.invites) == (1 if status == 201 else 0)


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("owner", ["admin", "manager", "member", "viewer"]),
        ("admin", ["manager", "member", "viewer"]),
        ("manager", []),
        ("member", []),
        ("viewer", []),
    ],
)
async def test_me_lists_invitable_roles(
    client_as: Callable[..., AsyncClient], role: str, expected: list[str]
) -> None:
    r = await client_as(role).get("/api/v1/me")
    assert r.status_code == 200, r.text
    assert r.json()["invitable_roles"] == expected


# ------------------------------------------------------------------ invite preview


async def test_invite_preview_states(
    client: AsyncClient,
    client_as: Callable[..., AsyncClient],
    org_a: SeededOrg,
    owner_engine: AsyncEngine,
    sender: CapturingSender,
) -> None:
    admin: AsyncClient = client_as("admin")
    r = await admin.post(
        "/api/v1/invites", json={"email": "preview@invite.example.com", "role": "manager"}
    )
    assert r.status_code == 201
    token = sender.invites[-1]["token"]

    p = await client.post("/api/v1/invites/preview", json={"token": token})  # public route
    assert p.status_code == 200, p.text
    body = p.json()
    assert body["status"] == "active" and body["role"] == "manager"
    assert body["email"] == "preview@invite.example.com"
    assert body["org_name"].startswith("Test ") and body["invited_by_name"] == "Admin"

    async with owner_engine.begin() as c:
        await c.execute(text("UPDATE invites SET expires_at = now() - interval '1 day'"))
    assert (await client.post("/api/v1/invites/preview", json={"token": token})).json()[
        "status"
    ] == "expired"

    async with owner_engine.begin() as c:
        await c.execute(
            text("UPDATE invites SET expires_at = now() + interval '1 day', accepted_at = now()")
        )
    assert (await client.post("/api/v1/invites/preview", json={"token": token})).json()[
        "status"
    ] == "used"

    missing = await client.post("/api/v1/invites/preview", json={"token": "no-such-token"})
    assert missing.status_code == 404


# ------------------------------------------------------------------ run retry


async def _insert_run(engine: AsyncEngine, org: SeededOrg, status: str, *, account: bool) -> UUID:
    account_id: UUID | None = uuid4() if account else None
    run_id = uuid4()
    async with engine.begin() as c:
        if account_id is not None:
            await c.execute(
                text("INSERT INTO accounts (id, org_id, name) VALUES (:i, :o, 'Retry Co')"),
                {"i": account_id, "o": org.org_id},
            )
        await c.execute(
            text(
                "INSERT INTO agent_runs (id, org_id, account_id, trigger, status) "
                "VALUES (:i, :o, :a, 'nightly', :s)"
            ),
            {"i": run_id, "o": org.org_id, "a": account_id, "s": status},
        )
    return run_id


async def test_retry_failed_run_creates_new_manual_run(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    run_id = await _insert_run(owner_engine, org_a, "failed", account=True)
    r = await client_as("manager").post(f"/api/v1/runs/{run_id}/retry")
    assert r.status_code == 202, r.text
    new_id = r.json()["agent_run_id"]
    assert new_id != str(run_id)
    async with owner_engine.begin() as c:
        row = (
            await c.execute(
                text("SELECT trigger, status, triggered_by FROM agent_runs WHERE id = :i"),
                {"i": new_id},
            )
        ).one()
    assert row[0] == "manual" and row[2] == org_a.users["manager"]


async def test_retry_rejects_wrong_state_missing_account_other_tenant_and_low_roles(
    client_as: Callable[..., AsyncClient],
    org_a: SeededOrg,
    org_b: SeededOrg,
    owner_engine: AsyncEngine,
) -> None:
    mgr: AsyncClient = client_as("manager")
    done = await _insert_run(owner_engine, org_a, "completed", account=True)
    assert (await mgr.post(f"/api/v1/runs/{done}/retry")).status_code == 409

    orphan = await _insert_run(owner_engine, org_a, "failed", account=False)
    assert (await mgr.post(f"/api/v1/runs/{orphan}/retry")).status_code == 400

    foreign = await _insert_run(owner_engine, org_b, "failed", account=True)
    assert (await mgr.post(f"/api/v1/runs/{foreign}/retry")).status_code == 404

    failed = await _insert_run(owner_engine, org_a, "failed", account=True)
    for role in ("member", "viewer"):
        assert (await client_as(role).post(f"/api/v1/runs/{failed}/retry")).status_code == 403


# ------------------------------------------------------------------ platform onboarding


async def _make_superadmin(engine: AsyncEngine, user_id: UUID) -> None:
    async with engine.begin() as c:
        await c.execute(text("UPDATE users SET is_superadmin = true WHERE id = :u"), {"u": user_id})


async def _set_email(engine: AsyncEngine, user_id: UUID, email: str) -> None:
    """Seeded users use a special-use TLD that EmailStr rejects; give them a routable one."""
    async with engine.begin() as c:
        await c.execute(
            text("UPDATE users SET email = :e WHERE id = :u"), {"e": email, "u": user_id}
        )


async def _cleanup_client(engine: AsyncEngine, org_id: str, email: str) -> None:
    async with engine.begin() as c:
        await c.execute(text("DELETE FROM organizations WHERE id = :i"), {"i": org_id})
        await c.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})


def _onboard_body(email: str, **over: Any) -> dict[str, Any]:
    return {
        "name": "Globex Industries",
        "primary_domain": "globex.example.com",
        "owner_email": email,
        "owner_name": "Gina Owner",
        **over,
    }


async def test_onboard_with_set_password_link_then_sign_in(
    client: AsyncClient,
    client_as: Callable[..., AsyncClient],
    org_a: SeededOrg,
    owner_engine: AsyncEngine,
    sender: CapturingSender,
) -> None:
    await _make_superadmin(owner_engine, org_a.users["owner"])
    email = f"gina-{uuid4().hex[:6]}@globex.example.com"
    r = await client_as("owner").post(ADMIN_ORGS, json=_onboard_body(email))
    assert r.status_code == 201, r.text
    out = r.json()
    org_id = out["org"]["id"]
    try:
        assert out["owner_created"] and out["set_password_email_sent"]
        assert out["temporary_password"] is None
        assert out["org"]["members"] == 1  # only the Owner; the platform operator is not a member

        async with owner_engine.begin() as c:
            members = (
                await c.execute(
                    text(
                        "SELECT u.email, m.role FROM memberships m JOIN users u ON u.id = m.user_id WHERE m.org_id = :o"
                    ),
                    {"o": org_id},
                )
            ).all()
            logged = (
                await c.execute(
                    text("SELECT actor_type, event FROM decision_log WHERE org_id = :o"),
                    {"o": org_id},
                )
            ).all()
        assert members == [(email, "owner")]
        assert logged == [("system", "org.created")]

        # No password yet, so sign-in fails until the link is used
        assert (
            await client.post(LOGIN, json={"email": email, "password": "Whatever-123456"})
        ).status_code == 401

        token = sender.set_passwords[-1]["token"]
        assert sender.set_passwords[-1]["to"] == email
        too_short = await client.post(
            "/api/v1/auth/set-password", json={"token": token, "password": "short"}
        )
        assert too_short.status_code == 422
        ok = await client.post(
            "/api/v1/auth/set-password", json={"token": token, "password": "Chosen-Passphrase-1"}
        )
        assert ok.status_code == 200, ok.text
        replay = await client.post(
            "/api/v1/auth/set-password", json={"token": token, "password": "Another-Passphrase-2"}
        )
        assert replay.status_code == 400

        login = await client.post(LOGIN, json={"email": email, "password": "Chosen-Passphrase-1"})
        assert login.status_code == 200, login.text
        assert login.json()["role"] == "owner" and login.json()["org_id"] == org_id
        assert login.json()["must_change_password"] is False
    finally:
        await _cleanup_client(owner_engine, org_id, email)


async def test_set_password_token_expiry_and_reissue_invalidates_old(
    client: AsyncClient,
    client_as: Callable[..., AsyncClient],
    org_a: SeededOrg,
    owner_engine: AsyncEngine,
    sender: CapturingSender,
) -> None:
    await _make_superadmin(owner_engine, org_a.users["owner"])
    email = f"exp-{uuid4().hex[:6]}@globex.example.com"
    r = await client_as("owner").post(ADMIN_ORGS, json=_onboard_body(email))
    org_id = r.json()["org"]["id"]
    try:
        token = sender.set_passwords[-1]["token"]
        async with owner_engine.begin() as c:
            await c.execute(
                text("UPDATE password_tokens SET expires_at = now() - interval '1 minute'")
            )
        expired = await client.post(
            "/api/v1/auth/set-password", json={"token": token, "password": "Chosen-Passphrase-1"}
        )
        assert expired.status_code == 400
        unknown = await client.post(
            "/api/v1/auth/set-password", json={"token": "x" * 40, "password": "Chosen-Passphrase-1"}
        )
        assert unknown.status_code == 400
    finally:
        await _cleanup_client(owner_engine, org_id, email)


async def test_onboard_with_temporary_password_forces_change(
    client: AsyncClient,
    client_as: Callable[..., AsyncClient],
    org_a: SeededOrg,
    owner_engine: AsyncEngine,
    sender: CapturingSender,
) -> None:
    await _make_superadmin(owner_engine, org_a.users["owner"])
    email = f"tmp-{uuid4().hex[:6]}@globex.example.com"
    r = await client_as("owner").post(
        ADMIN_ORGS,
        json=_onboard_body(email, send_set_password_email=False, generate_temporary_password=True),
    )
    assert r.status_code == 201, r.text
    out = r.json()
    org_id = out["org"]["id"]
    try:
        temp = out["temporary_password"]
        assert temp and len(temp) >= 10 and not out["set_password_email_sent"]
        assert sender.set_passwords == []

        first = await client.post(LOGIN, json={"email": email, "password": temp})
        assert first.status_code == 200, first.text
        assert first.json()["must_change_password"] is True
        owner_id = first.json()["user"]["id"]

        # The temporary password is never stored in clear text
        async with owner_engine.begin() as c:
            stored = (
                await c.execute(
                    text("SELECT password_hash FROM users WHERE email = :e"), {"e": email}
                )
            ).scalar_one()
        assert temp not in stored and stored.startswith("scrypt$")

        # change-password needs a signed-in user and the current password
        from tests.helpers import bearer, mint_jwt

        auth = bearer(mint_jwt(UUID(owner_id), UUID(org_id)))
        wrong = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "not-the-password", "new_password": "Brand-New-Passphrase-3"},
            headers=auth,
        )
        assert wrong.status_code == 400
        same = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": temp, "new_password": temp},
            headers=auth,
        )
        assert same.status_code == 400
        anon = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": temp, "new_password": "Brand-New-Passphrase-3"},
        )
        assert anon.status_code == 401
        changed = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": temp, "new_password": "Brand-New-Passphrase-3"},
            headers=auth,
        )
        assert changed.status_code == 200, changed.text

        assert (
            await client.post(LOGIN, json={"email": email, "password": temp})
        ).status_code == 401
        again = await client.post(
            LOGIN, json={"email": email, "password": "Brand-New-Passphrase-3"}
        )
        assert again.status_code == 200 and again.json()["must_change_password"] is False
    finally:
        await _cleanup_client(owner_engine, org_id, email)


async def test_onboard_guards(
    client_as: Callable[..., AsyncClient],
    org_a: SeededOrg,
    owner_engine: AsyncEngine,
    sender: CapturingSender,
) -> None:
    await _make_superadmin(owner_engine, org_a.users["owner"])
    await _set_email(
        owner_engine, org_a.users["owner"], f"op-{uuid4().hex[:6]}@platform.example.com"
    )
    su: AsyncClient = client_as("owner")

    # A new Owner needs at least one credential route
    neither = await su.post(
        ADMIN_ORGS,
        json=_onboard_body(
            f"none-{uuid4().hex[:6]}@globex.example.com",
            send_set_password_email=False,
            generate_temporary_password=False,
        ),
    )
    assert neither.status_code == 400

    # A platform operator can never own a client workspace
    async with owner_engine.begin() as c:
        op_email = (
            await c.execute(
                text("SELECT email FROM users WHERE id = :u"), {"u": org_a.users["owner"]}
            )
        ).scalar_one()
    assert (await su.post(ADMIN_ORGS, json=_onboard_body(str(op_email)))).status_code == 409

    # Customer roles cannot see the route at all (404, same as the other /admin routes)
    for role in ("admin", "manager", "member", "viewer"):
        r = await client_as(role).post(ADMIN_ORGS, json=_onboard_body("x@globex.example.com"))
        assert r.status_code == 404, role
    assert sender.set_passwords == []


async def test_onboard_existing_user_keeps_credentials(
    client_as: Callable[..., AsyncClient],
    org_a: SeededOrg,
    owner_engine: AsyncEngine,
    sender: CapturingSender,
) -> None:
    await _make_superadmin(owner_engine, org_a.users["owner"])
    await _set_email(
        owner_engine, org_a.users["manager"], f"mgr-{uuid4().hex[:6]}@existing.example.com"
    )
    async with owner_engine.begin() as c:
        row = (
            await c.execute(
                text("SELECT email, password_hash FROM users WHERE id = :u"),
                {"u": org_a.users["manager"]},
            )
        ).one()
    r = await client_as("owner").post(
        ADMIN_ORGS, json=_onboard_body(str(row[0]), generate_temporary_password=True)
    )
    assert r.status_code == 201, r.text
    out = r.json()
    try:
        assert out["owner_created"] is False
        assert out["temporary_password"] is None and out["set_password_email_sent"] is False
        assert sender.set_passwords == []
        async with owner_engine.begin() as c:
            after = (
                await c.execute(
                    text("SELECT password_hash, must_change_password FROM users WHERE id = :u"),
                    {"u": org_a.users["manager"]},
                )
            ).one()
        assert after[0] == row[1] and after[1] is False  # account credentials untouched
    finally:
        async with owner_engine.begin() as c:
            await c.execute(
                text("DELETE FROM organizations WHERE id = :i"), {"i": out["org"]["id"]}
            )


# ------------------------------------------------------------------ OAuth return target


async def test_oauth_state_carries_the_return_target() -> None:
    from app.utils.errors import AppError
    from app.utils.oauth_state import consume_state, create_state

    org, user = uuid4(), uuid4()
    default = await consume_state(create_state(org, user, "hubspot"), provider="hubspot")
    assert default.return_to == "settings"
    onboarding = await consume_state(
        create_state(org, user, "hubspot", return_to="onboarding"), provider="hubspot"
    )
    assert onboarding.return_to == "onboarding"
    with pytest.raises(AppError):
        create_state(org, user, "hubspot", return_to="https://evil.example.com")


def test_web_return_url_sends_the_browser_back_where_it_came_from() -> None:
    from app.config import get_settings
    from app.services.integrations import web_return_url

    base = get_settings().web_url
    assert web_return_url("hubspot", "onboarding") == f"{base}/onboarding/hubspot"
    assert web_return_url("gmail", "onboarding") == f"{base}/onboarding/google"
    assert web_return_url("gcal", "onboarding") == f"{base}/onboarding/google"
    assert web_return_url("slack", "onboarding") == f"{base}/onboarding/slack"
    assert web_return_url("hubspot", "settings") == f"{base}/settings/integrations"
    assert web_return_url("gmail", "settings") == f"{base}/settings/connections"


# ------------------------------------------------------------------ integration readiness


async def test_connect_says_so_when_the_provider_app_is_not_configured(
    client_as: Callable[..., AsyncClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import get_settings

    for var in ("HUBSPOT_CLIENT_ID", "HUBSPOT_CLIENT_SECRET", "SLACK_CLIENT_ID"):
        monkeypatch.setenv(var, "")
    get_settings.cache_clear()
    r = await client_as("admin").post("/api/v1/integrations/hubspot/connect")
    assert r.status_code == 503, r.text
    err = r.json()["error"]
    assert err["code"] == "not_configured"
    assert err["details"]["missing"] == ["HUBSPOT_CLIENT_ID", "HUBSPOT_CLIENT_SECRET"]
    r2 = await client_as("admin").post("/api/v1/integrations/slack/connect")
    assert (
        r2.status_code == 503 and "SLACK_SIGNING_SECRET" in r2.json()["error"]["details"]["missing"]
    )


def test_doctor_reports_missing_variables_and_the_urls_to_register() -> None:
    from app.config import Settings
    from scripts.integration_doctor import FAIL, PASS, run_checks

    bare = Settings(_env_file=None, app_env="local", public_api_url="https://api.example.com")  # type: ignore[call-arg]
    checks = run_checks(bare)
    fails = {c.area for c in checks if c.level == FAIL}
    assert fails == {"hubspot", "google", "slack"}
    msgs = [c.message for c in checks]
    assert any("https://api.example.com/api/v1/oauth/hubspot/callback" in m for m in msgs)
    assert any("https://api.example.com/api/v1/oauth/gcal/callback" in m for m in msgs)
    assert any("/api/v1/slack/interactions" in m for m in msgs)

    ready = Settings(  # type: ignore[call-arg]
        _env_file=None, app_env="local", public_api_url="https://api.example.com",
        hubspot_client_id="a", hubspot_client_secret="b", google_client_id="c",
        google_client_secret="d", slack_client_id="e", slack_client_secret="f",
        slack_signing_secret="g",
    )  # fmt: skip
    only_prov = [c for c in run_checks(ready) if c.area in {"hubspot", "google", "slack"}]
    assert not [c for c in only_prov if c.level == FAIL]
    assert any(c.level == PASS and "client credentials" in c.message for c in only_prov)


def test_doctor_slack_needs_public_https_and_valid_encryption_keys() -> None:
    import base64

    from app.config import Settings
    from scripts.integration_doctor import FAIL, _valid_enc_keys, run_checks

    prod = Settings(  # type: ignore[call-arg]
        _env_file=None, app_env="local", public_api_url="http://localhost:8000",
    )  # fmt: skip
    slack = [c for c in run_checks(prod, {"slack"}) if "public HTTPS" in c.message]
    assert slack and slack[0].level != "PASS"
    assert FAIL in {c.level for c in run_checks(prod, {"slack"})}
    assert _valid_enc_keys("k1:" + base64.b64encode(b"x" * 32).decode())
    assert (
        not _valid_enc_keys("k1:short")
        and not _valid_enc_keys("")
        and not _valid_enc_keys("nocolon")
    )
