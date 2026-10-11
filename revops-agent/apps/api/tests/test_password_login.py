"""Email + password sign-in / sign-up (POST /auth/login, /auth/signup) for every role."""

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.passwords import hash_password, verify_password
from tests.helpers import ROLES, SeededOrg, bearer, mint_jwt

PASSWORD = "correct-horse-battery"
LOGIN = "/api/v1/auth/login"
ADMIN_LOGIN = "/api/v1/auth/admin/login"
SIGNUP = "/api/v1/auth/signup"


async def _set_password(engine: AsyncEngine, user_id: UUID, password: str = PASSWORD) -> str:
    async with engine.begin() as c:
        email = (
            await c.execute(
                text("UPDATE users SET password_hash = :h WHERE id = :u RETURNING email"),
                {"h": hash_password(password), "u": user_id},
            )
        ).scalar_one()
    return str(email)


async def _login(client: AsyncClient, email: str, password: str = PASSWORD):  # type: ignore[no-untyped-def]
    return await client.post(LOGIN, json={"email": email, "password": password})


def test_password_hash_roundtrip_and_format() -> None:
    h = hash_password("s3cret-passphrase")
    assert h.startswith("scrypt$") and "s3cret" not in h
    assert verify_password("s3cret-passphrase", h)
    assert not verify_password("S3cret-passphrase", h)
    assert hash_password("s3cret-passphrase") != h  # per-hash salt
    assert not verify_password("x", "not-a-hash") and not verify_password("x", "bcrypt$1$2$3$a$b")


@pytest.mark.parametrize("role", ROLES)
async def test_each_workspace_role_signs_in_and_gets_that_role(
    client: AsyncClient, seeded: SeededOrg, owner_engine: AsyncEngine, role: str
) -> None:
    email = await _set_password(owner_engine, seeded.users[role])
    r = await _login(client, email.upper())  # emails are case-insensitive
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["id"] == str(seeded.users[role])
    assert body["org_id"] == str(seeded.org_id)
    assert body["role"] == role
    assert body["is_superadmin"] is False and body["needs_onboarding"] is False
    assert [m["role"] for m in body["memberships"]] == [role]

    # the identity from sign-in is enough to call the API; the role is re-read from the DB
    token = mint_jwt(UUID(body["user"]["id"]), UUID(body["org_id"]), role="owner")
    me = (await client.get("/api/v1/me", headers=bearer(token))).json()
    assert me["role"] == role


async def test_superadmin_signs_in_only_through_the_platform_portal(
    client: AsyncClient, seeded: SeededOrg, owner_engine: AsyncEngine
) -> None:
    uid = uuid4()
    email = f"root-{uid.hex[:8]}@example.test"
    async with owner_engine.begin() as c:
        await c.execute(
            text(
                "INSERT INTO users (id, email, name, is_superadmin, password_hash) "
                "VALUES (:i, :e, 'Root', true, :h)"
            ),
            {"i": uid, "e": email, "h": hash_password(PASSWORD)},
        )
    try:
        # customer portal refuses a superadmin, exactly like a wrong password
        r = await _login(client, email)
        assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_credentials"

        r = await client.post(ADMIN_LOGIN, json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["is_superadmin"] is True and body["role"] is None
        assert body["memberships"] == [] and body["needs_onboarding"] is False
        token = mint_jwt(uid, UUID(body["org_id"]))
        assert (await client.get("/api/v1/admin/orgs", headers=bearer(token))).status_code == 200
        me = (await client.get("/api/v1/admin/me", headers=bearer(token))).json()
        assert me["email"] == email and "platform:admin" in me["permissions"]
        assert me["environment"] in {"local", "test", "staging", "prod"}
        # a superadmin has no customer identity at all
        assert (await client.get("/api/v1/me", headers=bearer(token))).status_code == 403
    finally:
        async with owner_engine.begin() as c:
            await c.execute(text("DELETE FROM users WHERE id = :i"), {"i": uid})


async def test_customer_roles_cannot_use_the_platform_portal(
    client: AsyncClient, seeded: SeededOrg, owner_engine: AsyncEngine
) -> None:
    for role in ROLES:
        email = await _set_password(owner_engine, seeded.users[role])
        r = await client.post(ADMIN_LOGIN, json={"email": email, "password": PASSWORD})
        assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_credentials", role
        token = mint_jwt(seeded.users[role], seeded.org_id)
        assert (await client.get("/api/v1/admin/me", headers=bearer(token))).status_code == 404


async def test_wrong_password_and_unknown_email_are_indistinguishable(
    client: AsyncClient, seeded: SeededOrg, owner_engine: AsyncEngine
) -> None:
    email = await _set_password(owner_engine, seeded.users["member"])
    wrong = await _login(client, email, "wrong-password-1")
    unknown = await _login(client, f"nobody-{uuid4().hex[:6]}@example.test")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"] == "invalid_credentials"
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]


async def test_user_without_a_password_cannot_sign_in(
    client: AsyncClient, seeded: SeededOrg, owner_engine: AsyncEngine
) -> None:
    async with owner_engine.begin() as c:
        email = (
            await c.execute(
                text("SELECT email FROM users WHERE id = :u"), {"u": seeded.users["admin"]}
            )
        ).scalar_one()
    r = await _login(client, str(email), "")  # empty is rejected by validation
    assert r.status_code == 422
    r = await _login(client, str(email), "anything-at-all")
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_credentials"


async def test_account_locks_after_repeated_failures_even_for_the_right_password(
    client: AsyncClient, seeded: SeededOrg, owner_engine: AsyncEngine
) -> None:
    email = await _set_password(owner_engine, seeded.users["manager"])
    for _ in range(5):
        assert (await _login(client, email, "bad-password-xx")).status_code == 401
    r = await _login(client, email)
    assert r.status_code == 429 and r.json()["error"]["code"] == "account_locked"
    assert int(r.headers["retry-after"]) > 0
    async with owner_engine.begin() as c:
        await c.execute(
            text("UPDATE users SET locked_until = now() - interval '1 minute' WHERE id = :u"),
            {"u": seeded.users["manager"]},
        )
    assert (await _login(client, email)).status_code == 200


async def test_successful_login_resets_the_failure_counter(
    client: AsyncClient, seeded: SeededOrg, owner_engine: AsyncEngine
) -> None:
    email = await _set_password(owner_engine, seeded.users["viewer"])
    for _ in range(4):
        await _login(client, email, "bad-password-xx")
    assert (await _login(client, email)).status_code == 200
    for _ in range(4):
        await _login(client, email, "bad-password-xx")
    assert (await _login(client, email)).status_code == 200  # never reached 5 in a row


async def test_disabled_membership_cannot_sign_in(
    client: AsyncClient, seeded: SeededOrg, owner_engine: AsyncEngine
) -> None:
    email = await _set_password(owner_engine, seeded.users["member"])
    async with owner_engine.begin() as c:
        await c.execute(
            text("UPDATE memberships SET status = 'disabled' WHERE user_id = :u"),
            {"u": seeded.users["member"]},
        )
    r = await _login(client, email)
    assert r.status_code == 403 and r.json()["error"]["code"] == "account_disabled"


async def test_signup_creates_account_then_login_needs_onboarding(
    client: AsyncClient, owner_engine: AsyncEngine
) -> None:
    email = f"new-{uuid4().hex[:8]}@example.com"
    try:
        r = await client.post(
            SIGNUP, json={"name": " Nora New ", "email": email, "password": PASSWORD}
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["user"]["email"] == email and body["user"]["name"] == "Nora New"
        assert body["needs_onboarding"] is True and body["is_superadmin"] is False
        assert body["role"] is None and body["memberships"] == []

        again = await _login(client, email)
        assert again.status_code == 200 and again.json()["needs_onboarding"] is True

        # the new user can create a workspace and then signs in as its owner
        token = mint_jwt(UUID(body["user"]["id"]), UUID(body["org_id"]))
        org = await client.post("/api/v1/orgs", json={"name": "Nora Co"}, headers=bearer(token))
        assert org.status_code == 201, org.text
        after = (await _login(client, email)).json()
        assert after["role"] == "owner" and after["org_id"] == org.json()["id"]
        assert after["needs_onboarding"] is False
    finally:
        async with owner_engine.begin() as c:
            await c.execute(
                text(
                    "DELETE FROM organizations WHERE id IN (SELECT org_id FROM memberships m "
                    "JOIN users u ON u.id = m.user_id WHERE u.email = :e)"
                ),
                {"e": email},
            )
            await c.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})


async def test_signup_rejects_duplicates_and_weak_input(
    client: AsyncClient, owner_engine: AsyncEngine
) -> None:
    taken = f"taken-{uuid4().hex[:8]}@example.com"
    uid = uuid4()
    async with owner_engine.begin() as c:
        await c.execute(
            text("INSERT INTO users (id, email) VALUES (:i, :e)"), {"i": uid, "e": taken}
        )
    try:
        dup = await client.post(
            SIGNUP, json={"name": "Dup Licate", "email": taken.upper(), "password": PASSWORD}
        )
        assert dup.status_code == 409 and dup.json()["error"]["code"] == "conflict"

        ok_email = f"x-{uuid4().hex[:6]}@example.com"
        for bad in (
            {"name": "A", "email": ok_email, "password": PASSWORD},
            {"name": "Ok Name", "email": "not-an-email", "password": PASSWORD},
            {"name": "Ok Name", "email": ok_email, "password": "short"},
            {"name": "Ok Name", "email": ok_email, "password": "x" * 129},
        ):
            r = await client.post(SIGNUP, json=bad)
            assert r.status_code == 422, bad
    finally:
        async with owner_engine.begin() as c:
            await c.execute(text("DELETE FROM users WHERE id = :i"), {"i": uid})
