from uuid import uuid4

import pytest
from fastapi import APIRouter, Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.deps import (
    CurrentMembership,
    invalidate_membership,
    require_owner_or_role,
    require_permission,
    require_role,
)
from app.main import create_app
from app.permissions import Action
from tests.helpers import SeededOrg, bearer, mint_jwt


async def _me(client: AsyncClient, token: str | None):  # type: ignore[no-untyped-def]
    return await client.get("/api/v1/me", headers=bearer(token) if token else {})


async def test_me_returns_role_and_permissions_from_db(
    client: AsyncClient, seeded: SeededOrg
) -> None:
    token = mint_jwt(seeded.users["manager"], seeded.org_id)
    r = await _me(client, token)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["role"] == "manager"
    assert body["org"]["id"] == str(seeded.org_id)
    assert "approve:any" in body["permissions"] and "members:manage" not in body["permissions"]


async def test_missing_or_malformed_header_is_401(client: AsyncClient) -> None:
    for headers in ({}, {"Authorization": "Token abc"}, {"Authorization": "Bearer"}):
        r = await client.get("/api/v1/me", headers=headers)
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthenticated"


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"secret": "x" * 40}, "invalid_token"),
        ({"aud": "someone-else"}, "invalid_token"),
        ({"drop": ("sub",)}, "invalid_token"),
        ({"drop": ("org_id",)}, "invalid_token"),
        ({"drop": ("exp",)}, "invalid_token"),
        ({"drop": ("aud",)}, "invalid_token"),
        ({"exp_in": -120}, "token_expired"),
    ],
)
async def test_bad_tokens_are_401(
    client: AsyncClient, seeded: SeededOrg, kwargs: dict[str, object], code: str
) -> None:
    token = mint_jwt(seeded.users["owner"], seeded.org_id, **kwargs)  # type: ignore[arg-type]
    r = await _me(client, token)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == code


async def test_non_uuid_subject_is_401(client: AsyncClient, seeded: SeededOrg) -> None:
    token = mint_jwt(seeded.users["owner"], seeded.org_id, sub="not-a-uuid")
    assert (await _me(client, token)).status_code == 401


async def test_clock_skew_30s_is_tolerated(client: AsyncClient, seeded: SeededOrg) -> None:
    assert (
        await _me(client, mint_jwt(seeded.users["owner"], seeded.org_id, exp_in=-20))
    ).status_code == 200
    assert (
        await _me(client, mint_jwt(seeded.users["owner"], seeded.org_id, exp_in=-40))
    ).status_code == 401


async def test_role_claim_in_token_is_ignored(client: AsyncClient, seeded: SeededOrg) -> None:
    token = mint_jwt(seeded.users["viewer"], seeded.org_id, role="owner")
    r = await _me(client, token)
    assert r.json()["role"] == "viewer"


async def test_non_member_and_foreign_org_are_403(
    client: AsyncClient, seeded: SeededOrg, owner_engine: AsyncEngine
) -> None:
    stranger = mint_jwt(uuid4(), seeded.org_id)
    r = await _me(client, stranger)
    assert r.status_code == 403 and r.json()["error"]["code"] == "not_a_member"

    from tests.helpers import drop_org, seed_org

    other = await seed_org(owner_engine)
    try:  # a valid member of org B presenting a token for org A
        r = await _me(client, mint_jwt(other.users["owner"], seeded.org_id))
        assert r.status_code == 403
    finally:
        await drop_org(owner_engine, other)


async def test_disabled_member_is_403(
    client: AsyncClient, seeded: SeededOrg, owner_engine: AsyncEngine
) -> None:
    async with owner_engine.begin() as c:
        await c.execute(
            text("UPDATE memberships SET status='disabled' WHERE user_id=:u"),
            {"u": seeded.users["member"]},
        )
    r = await _me(client, mint_jwt(seeded.users["member"], seeded.org_id))
    assert r.status_code == 403


async def test_suspended_org_is_403_org_suspended(
    client: AsyncClient, owner_engine: AsyncEngine
) -> None:
    from tests.helpers import drop_org, seed_org

    s = await seed_org(owner_engine, status="suspended")
    try:
        r = await _me(client, mint_jwt(s.users["owner"], s.org_id))
        assert r.status_code == 403 and r.json()["error"]["code"] == "org_suspended"
    finally:
        await drop_org(owner_engine, s)


async def test_membership_cached_60s_and_invalidated_on_role_change(
    client: AsyncClient, seeded: SeededOrg, owner_engine: AsyncEngine
) -> None:
    uid = seeded.users["admin"]
    token = mint_jwt(uid, seeded.org_id)
    assert (await _me(client, token)).json()["role"] == "admin"
    async with owner_engine.begin() as c:
        await c.execute(text("UPDATE memberships SET role='viewer' WHERE user_id=:u"), {"u": uid})
    assert (await _me(client, token)).json()["role"] == "admin"  # still cached
    await invalidate_membership(uid, seeded.org_id)
    assert (await _me(client, token)).json()["role"] == "viewer"  # invalidated -> fresh from DB


def _guarded_app() -> FastAPI:
    app = create_app()
    r = APIRouter()

    @r.get("/t/admins")
    async def admins(m: CurrentMembership = Depends(require_role("admin"))) -> dict[str, str]:
        return {"role": m.role.value}

    @r.get("/t/owner-or-manager")
    async def om(
        m: CurrentMembership = Depends(require_owner_or_role("manager")),
    ) -> dict[str, str]:
        return {"role": m.role.value}

    @r.get("/t/members-manage")
    async def mm(
        m: CurrentMembership = Depends(require_permission(Action.MANAGE_MEMBERS)),
    ) -> dict[str, str]:
        return {"role": m.role.value}

    app.include_router(r)
    return app


@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("/t/admins", {"admin"}),
        ("/t/owner-or-manager", {"owner", "manager"}),
        ("/t/members-manage", {"owner", "admin"}),
    ],
)
async def test_role_and_permission_guards(seeded: SeededOrg, path: str, allowed: set[str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=_guarded_app()), base_url="http://t") as c:
        for role, uid in seeded.users.items():
            r = await c.get(path, headers=bearer(mint_jwt(uid, seeded.org_id)))
            if role in allowed:
                assert r.status_code == 200, (role, r.text)
            else:
                assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden", role
