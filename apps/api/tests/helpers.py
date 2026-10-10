"""Test helpers (superseded by the full harness in V0-16)."""

import time
from dataclasses import dataclass
from uuid import UUID, uuid4

import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import get_settings

ROLES = ["owner", "admin", "manager", "member", "viewer"]


@dataclass
class SeededOrg:
    org_id: UUID
    users: dict[str, UUID]  # role -> user id


async def seed_org(engine: AsyncEngine, status: str = "active") -> SeededOrg:
    """Insert an org and one user per role as the superuser (bypasses RLS)."""
    org_id = uuid4()
    users = {r: uuid4() for r in ROLES}
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO organizations (id, name, status) VALUES (:i, :n, :s)"),
            {"i": org_id, "n": f"Test {org_id.hex[:6]}", "s": status},
        )
        for role, uid in users.items():
            await conn.execute(
                text("INSERT INTO users (id, email, name) VALUES (:i, :e, :n)"),
                {"i": uid, "e": f"{role}-{uid.hex[:8]}@example.test", "n": role.title()},
            )
            await conn.execute(
                text("INSERT INTO memberships (id, org_id, user_id, role) VALUES (:i, :o, :u, :r)"),
                {"i": uuid4(), "o": org_id, "u": uid, "r": role},
            )
    return SeededOrg(org_id, users)


async def drop_org(engine: AsyncEngine, seeded: SeededOrg) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM organizations WHERE id = :i"), {"i": seeded.org_id})
        await conn.execute(
            text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids": list(seeded.users.values())}
        )


def mint_jwt(
    user_id: UUID,
    org_id: UUID,
    *,
    secret: str | None = None,
    aud: str | None = None,
    exp_in: int = 300,
    drop: tuple[str, ...] = (),
    **extra: object,
) -> str:
    s = get_settings()
    now = int(time.time())
    claims: dict[str, object] = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "aud": aud or s.api_jwt_audience,
        "iat": now,
        "exp": now + exp_in,
        **extra,
    }
    for k in drop:
        claims.pop(k, None)
    return jwt.encode(claims, secret or s.api_jwt_secret, algorithm="HS256")


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
