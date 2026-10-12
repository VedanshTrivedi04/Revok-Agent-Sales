import hashlib
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.session import org_session
from app.models.actions import AutonomyPolicy
from app.models.tenancy import ApiKey, Invite, Organization
from app.schemas.identity import (
    InviteCreateIn,
)
from app.services.api_keys import verify_api_key
from app.services.invites import create_invite
from app.services.notifications import notify
from app.utils.errors import AppError
from tests.helpers import SeededOrg, assert_logged, bearer, mint_jwt

# =====================================================================
# V1-01: GET /me and PATCH /me
# =====================================================================


async def test_get_me_cross_org_and_flags(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    # Add owner of org_a as a member of another org
    other_org_id = uuid4()
    async with owner_engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO organizations (id, name, status) VALUES (:i, :n, 'active')"),
            {"i": other_org_id, "n": "Other Org"},
        )
        await conn.execute(
            text(
                "INSERT INTO memberships (id, org_id, user_id, role, status) VALUES (:i, :o, :u, 'admin', 'active')"
            ),
            {"i": uuid4(), "o": other_org_id, "u": org_a.users["owner"]},
        )

    client: AsyncClient = client_as("owner")  # type: ignore[operator]
    r = await client.get("/api/v1/me")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["role"] == "owner"
    assert data["org"]["id"] == str(org_a.org_id)
    assert "approve:any" in data["permissions"]
    assert "onboarding" in data and data["onboarding"] is not None
    assert data["portals"] == ["control"] and data["home"] == "/control/overview"
    assert "analytics:view" in data["permissions"]

    # Check cross-org memberships list contains both orgs
    org_ids = [m["org_id"] for m in data["memberships"]]
    assert str(org_a.org_id) in org_ids
    assert str(other_org_id) in org_ids


async def test_patch_me(client_as: Callable[..., AsyncClient], org_a: SeededOrg) -> None:
    client: AsyncClient = client_as("manager")  # type: ignore[operator]
    patch_payload = {
        "name": "Updated Manager Name",
        "timezone": "Europe/London",
        "notification_prefs": {
            "digest_channel": "email",
            "digest_hour": 10,
            "digest_days": "daily",
            "alert_high": True,
            "alert_assigned": False,
            "alert_failed": True,
        },
    }
    r = await client.patch("/api/v1/me", json=patch_payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["user"]["name"] == "Updated Manager Name"
    assert data["user"]["timezone"] == "Europe/London"
    assert data["user"]["notification_prefs"]["digest_channel"] == "email"
    assert data["user"]["notification_prefs"]["alert_assigned"] is False


# =====================================================================
# V1-02: POST /orgs, GET/PATCH/DELETE /orgs/current
# =====================================================================


async def test_create_org_in_one_transaction(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    client: AsyncClient = client_as("owner")  # type: ignore[operator]
    payload = {
        "name": "New Venture Corp",
        "primary_domain": "newventure.io",
        "timezone": "America/New_York",
        "currency": "USD",
    }
    r = await client.post("/api/v1/orgs", json=payload)
    assert r.status_code == 201, r.text
    data = r.json()
    new_org_id = UUID(data["id"])
    assert data["name"] == "New Venture Corp"
    assert data["primary_domain"] == "newventure.io"

    # Verify audit log was written in the same transaction
    await assert_logged(new_org_id, "org.created", entity_id=new_org_id, times=1)

    # Verify default autonomy policies were seeded
    async with org_session(new_org_id) as s:
        policies = (
            (await s.execute(select(AutonomyPolicy).where(AutonomyPolicy.org_id == new_org_id)))
            .scalars()
            .all()
        )
        assert len(policies) == 6
        action_types = {p.action_type for p in policies}
        assert {
            "email_draft",
            "crm_task",
            "crm_field_update",
            "crm_note",
            "slack_internal",
            "meeting_request",
        } <= action_types


async def test_get_and_patch_current_org(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    client: AsyncClient = client_as("admin")  # type: ignore[operator]
    r = await client.get("/api/v1/orgs/current")
    assert r.status_code == 200
    assert r.json()["id"] == str(org_a.org_id)

    # Admin patches org settings
    patch_body = {
        "name": "Renamed Org",
        "timezone": "UTC",
        "settings": {
            "digest_hour": 8,
            "card_expiry_days": 14,
            "backfill_days": 60,
            "nightly_hour": 3,
        },
    }
    r_patch = await client.patch("/api/v1/orgs/current", json=patch_body)
    assert r_patch.status_code == 200
    assert r_patch.json()["name"] == "Renamed Org"
    assert r_patch.json()["settings"]["digest_hour"] == 8
    await assert_logged(org_a.org_id, "org.updated", entity_id=org_a.org_id, times=1)


async def test_delete_current_org(client_as: Any, org_a: SeededOrg) -> None:
    # Manager cannot delete org
    mgr_client: AsyncClient = client_as("manager")
    r_mgr = await mgr_client.request("DELETE", "/api/v1/orgs/current", json={"confirm": "Whatever"})
    assert r_mgr.status_code == 403

    # Admin cannot delete org (owner only)
    admin_client: AsyncClient = client_as("admin")
    r_admin = await admin_client.request(
        "DELETE", "/api/v1/orgs/current", json={"confirm": "Whatever"}
    )
    assert r_admin.status_code == 403

    owner_client: AsyncClient = client_as("owner")
    # Name mismatch -> 422
    r_bad = await owner_client.request(
        "DELETE", "/api/v1/orgs/current", json={"confirm": "Wrong Name"}
    )
    assert r_bad.status_code == 422

    # Get current name
    r_get = await owner_client.get("/api/v1/orgs/current")
    org_name = r_get.json()["name"]

    # Delete with matching confirmation
    r_del = await owner_client.request("DELETE", "/api/v1/orgs/current", json={"confirm": org_name})
    assert r_del.status_code == 200
    assert r_del.json()["ok"] is True
    await assert_logged(org_a.org_id, "org.deleted", entity_id=org_a.org_id, times=1)

    # Next call should return not_found or deleted
    async with org_session(org_a.org_id) as s:
        org = await s.get(Organization, org_a.org_id)
        assert org is not None and org.status == "deleted"


# =====================================================================
# V1-03: Members (list, patch, delete, last owner rules)
# =====================================================================


async def test_list_members_pagination(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    client: AsyncClient = client_as("viewer")  # type: ignore[operator]
    r = await client.get("/api/v1/members?limit=3")
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 3
    assert data["next_cursor"] is not None

    # Fetch next page
    r2 = await client.get(f"/api/v1/members?limit=3&cursor={data['next_cursor']}")
    assert r2.status_code == 200
    assert len(r2.json()["items"]) >= 1


async def test_patch_member_last_owner_protection(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    owner_client: AsyncClient = client_as("owner")  # type: ignore[operator]
    r_members = await owner_client.get("/api/v1/members")
    owner_m = next(m for m in r_members.json()["items"] if m["role"] == "owner")

    # Demoting last owner -> 409 last_owner_required
    r_demote = await owner_client.patch(f"/api/v1/members/{owner_m['id']}", json={"role": "admin"})
    assert r_demote.status_code == 409
    assert r_demote.json()["error"]["code"] == "last_owner_required"

    # Disabling last owner -> 409 last_owner_required
    r_disable = await owner_client.patch(
        f"/api/v1/members/{owner_m['id']}", json={"status": "disabled"}
    )
    assert r_disable.status_code == 409
    assert r_disable.json()["error"]["code"] == "last_owner_required"


async def test_admin_cannot_modify_or_remove_owner(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    admin_client: AsyncClient = client_as("admin")  # type: ignore[operator]
    r_members = await admin_client.get("/api/v1/members")
    owner_m = next(m for m in r_members.json()["items"] if m["role"] == "owner")

    # Admin modifying owner -> 403
    r_patch = await admin_client.patch(
        f"/api/v1/members/{owner_m['id']}", json={"crm_owner_id": "hs-999"}
    )
    assert r_patch.status_code == 403

    # Admin removing owner -> 403
    r_del = await admin_client.delete(f"/api/v1/members/{owner_m['id']}")
    assert r_del.status_code == 403


async def test_owner_transfers_ownership_and_removes_member(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    owner_client: AsyncClient = client_as("owner")  # type: ignore[operator]
    r_members = await owner_client.get("/api/v1/members")
    admin_m = next(m for m in r_members.json()["items"] if m["role"] == "admin")

    # Promote admin to owner
    r_promote = await owner_client.patch(f"/api/v1/members/{admin_m['id']}", json={"role": "owner"})
    assert r_promote.status_code == 200
    assert r_promote.json()["role"] == "owner"
    await assert_logged(org_a.org_id, "member.updated", entity_id=UUID(admin_m["id"]))

    # Now there are 2 owners; owner can demote the first owner
    owner_m = next(m for m in r_members.json()["items"] if m["role"] == "owner")
    r_demote = await owner_client.patch(f"/api/v1/members/{owner_m['id']}", json={"role": "admin"})
    assert r_demote.status_code == 200

    # Delete viewer member
    viewer_m = next(m for m in r_members.json()["items"] if m["role"] == "viewer")
    r_del = await owner_client.delete(f"/api/v1/members/{viewer_m['id']}")
    assert r_del.status_code == 200
    await assert_logged(org_a.org_id, "member.removed", entity_id=UUID(viewer_m["id"]))


# =====================================================================
# V1-04: Invites
# =====================================================================


async def test_create_invite_and_rate_limit(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    admin_client: AsyncClient = client_as("admin")  # type: ignore[operator]
    target_email = "newhire@example.com"

    # Send 3 invites
    for _ in range(3):
        r = await admin_client.post(
            "/api/v1/invites", json={"email": target_email, "role": "member"}
        )
        assert r.status_code == 201
        assert r.json()["email"] == target_email
        assert r.json()["role"] == "member"

    # 4th invite -> 429 rate_limited
    r_4th = await admin_client.post(
        "/api/v1/invites", json={"email": target_email, "role": "member"}
    )
    assert r_4th.status_code == 429
    assert r_4th.json()["error"]["code"] == "rate_limited"


async def test_invite_accept_flow_and_replay_protection(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    # 1. Admin creates invite via service to get the plaintext token
    async with org_session(org_a.org_id) as s:
        invite_out = await create_invite(
            s,
            org_a.org_id,
            InviteCreateIn(email="invited@example.com", role="manager"),
            org_a.users["admin"],
            "admin",
        )

    # Find the token hash
    async with org_session(org_a.org_id) as s:
        inv_row = await s.get(Invite, invite_out.id)
        assert inv_row is not None
        # We know create_invite hashes token; let's test accepting with correct token
        # In service create_invite: token was sent via email. Let's create an invite with a known token:
        test_token = "secret-token-32-chars-long-abc-123456"
        token_hash = hashlib.sha256(test_token.encode()).hexdigest()
        inv_row.token_hash = token_hash
        await s.flush()

    # 2. Create a user with matching email
    user_id = uuid4()
    async with owner_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, email, name) VALUES (:i, 'invited@example.com', 'Invited User')"
            ),
            {"i": user_id},
        )

    # 3. User with mismatched email tries to accept -> 403
    other_user_id = uuid4()
    async with owner_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, email, name) VALUES (:i, 'stranger@example.com', 'Stranger')"
            ),
            {"i": other_user_id},
        )

    owner_c: AsyncClient = client_as("owner")
    stranger_token = mint_jwt(other_user_id, org_a.org_id, email="stranger@example.com")
    stranger_client = AsyncClient(
        transport=owner_c._transport,
        base_url="http://t",
        headers=bearer(stranger_token),
    )
    r_bad_email = await stranger_client.post("/api/v1/invites/accept", json={"token": test_token})
    assert r_bad_email.status_code == 403

    # 4. User with matching email accepts -> 200
    matching_token = mint_jwt(user_id, org_a.org_id, email="invited@example.com")
    matching_client = AsyncClient(
        transport=owner_c._transport,
        base_url="http://t",
        headers=bearer(matching_token),
    )
    r_accept = await matching_client.post("/api/v1/invites/accept", json={"token": test_token})
    assert r_accept.status_code == 200
    assert r_accept.json()["org_id"] == str(org_a.org_id)
    assert r_accept.json()["role"] == "manager"
    await assert_logged(org_a.org_id, "invite.accepted", entity_id=invite_out.id)

    # 5. Token replay protection: second accept -> 409 conflict
    r_replay = await matching_client.post("/api/v1/invites/accept", json={"token": test_token})
    assert r_replay.status_code == 409
    assert r_replay.json()["error"]["code"] == "conflict"


# =====================================================================
# V1-05: API Keys
# =====================================================================


async def test_api_key_lifecycle_and_hashing(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    admin_client: AsyncClient = client_as("admin")  # type: ignore[operator]

    # Create API key
    r_create = await admin_client.post("/api/v1/api-keys", json={"name": "Ingest Pipeline"})
    assert r_create.status_code == 201
    created = r_create.json()
    plaintext_key = created["key"]
    assert plaintext_key.startswith("rk_live_")
    key_id = UUID(created["id"])

    # Verify sha256 hash was stored, not plaintext
    async with org_session(org_a.org_id) as s:
        db_key = await s.get(ApiKey, key_id)
        assert db_key is not None
        assert db_key.key_hash == hashlib.sha256(plaintext_key.encode()).hexdigest()
        assert db_key.key_hash != plaintext_key

    # List API keys returns prefix only (no plaintext key)
    r_list = await admin_client.get("/api/v1/api-keys")
    assert r_list.status_code == 200
    keys = r_list.json()
    assert any(k["id"] == str(key_id) for k in keys)
    assert all("key" not in k for k in keys)

    # Verify key authentication dependency works
    org_id, scopes = await verify_api_key(plaintext_key)
    assert org_id == org_a.org_id
    assert "ingest:usage" in scopes

    # Revoke key
    r_rev = await admin_client.delete(f"/api/v1/api-keys/{key_id}")
    assert r_rev.status_code == 200

    # Verification fails on revoked key -> 401
    with pytest.raises(AppError) as exc_info:
        await verify_api_key(plaintext_key)
    assert exc_info.value.code == "unauthenticated"


# =====================================================================
# V1-06: Notifications
# =====================================================================


async def test_notifications_service_and_endpoints(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    member_user = org_a.users["member"]

    # Insert notifications via service
    async with org_session(org_a.org_id) as s:
        n1 = await notify(
            s,
            org_id=org_a.org_id,
            user_id=member_user,
            kind="finding_high",
            title="High Churn Risk: Acme Corp",
            body="Renewal in 43 days with usage drop",
        )
        await notify(
            s,
            org_id=org_a.org_id,
            user_id=member_user,
            kind="card_assigned",
            title="Action card assigned",
            body="Review draft email",
        )

    member_client: AsyncClient = client_as("member")  # type: ignore[operator]

    # List notifications
    r = await member_client.get("/api/v1/notifications?unread=true")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 2
    assert all(i["read_at"] is None for i in items)

    # Mark one read
    r_read1 = await member_client.post("/api/v1/notifications/read", json={"ids": [str(n1.id)]})
    assert r_read1.status_code == 200

    # Mark all read
    r_read_all = await member_client.post("/api/v1/notifications/read", json={"all": True})
    assert r_read_all.status_code == 200

    # Unread list is now empty
    r_empty = await member_client.get("/api/v1/notifications?unread=true")
    assert len(r_empty.json()["items"]) == 0


# =====================================================================
# Table-driven role permission tests for Phase 1 endpoints
# =====================================================================


@pytest.mark.parametrize(
    ("role", "expected_status"),
    [
        ("owner", 200),
        ("admin", 200),
        ("manager", 403),
        ("member", 403),
        ("viewer", 403),
    ],
)
async def test_members_manage_permission_matrix(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg, role: str, expected_status: int
) -> None:
    client: AsyncClient = client_as(role)  # type: ignore[operator]
    # Invite requires MANAGE_MEMBERS
    r = await client.post("/api/v1/invites", json={"email": f"{role}@test.com", "role": "member"})
    assert r.status_code == (201 if expected_status == 200 else expected_status)


@pytest.mark.parametrize(
    ("role", "expected_status"),
    [
        ("owner", 200),
        ("admin", 200),
        ("manager", 403),
        ("member", 403),
        ("viewer", 403),
    ],
)
async def test_api_keys_permission_matrix(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg, role: str, expected_status: int
) -> None:
    client: AsyncClient = client_as(role)
    r = await client.get("/api/v1/api-keys")
    assert r.status_code == expected_status
