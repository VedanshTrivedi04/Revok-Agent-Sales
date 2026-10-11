"""Email + password sign-in and sign-up.

Users are global (no RLS) so everything here runs in `admin_session()`. The API never trusts a
client-chosen role: it returns the identity and default workspace, and every later request
re-reads the membership role from the DB (see app/auth/deps.py).
"""

import hashlib
import secrets
from datetime import timedelta
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password_async, verify_password_async
from app.db.session import admin_session
from app.models.tenancy import Membership, Organization, PasswordToken, User
from app.permissions import PORTAL_HOME, PORTAL_WORK, Role, home_for
from app.schemas.identity import (
    Ack,
    AuthSession,
    AuthUser,
    ChangePasswordIn,
    LoginIn,
    MeMembership,
    SetPasswordIn,
    SignupIn,
)
from app.utils.errors import AppError
from app.utils.ids import new_id
from app.utils.time import utcnow

log = structlog.get_logger()

MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 15
NO_ORG = UUID(int=0)
SET_PASSWORD_TTL = timedelta(days=7)
_ROLE_RANK = {Role.OWNER: 0, Role.ADMIN: 1, Role.MANAGER: 2, Role.MEMBER: 3, Role.VIEWER: 4}


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def _workspaces(user_id: UUID) -> tuple[list[MeMembership], bool]:
    """Usable workspaces for the user (best role first) and whether any membership exists at all."""
    async with admin_session() as s:
        rows = (
            await s.execute(
                select(
                    Membership.org_id,
                    Organization.name,
                    Membership.role,
                    Membership.status,
                    Organization.status,
                    Membership.created_at,
                )
                .join(Organization, Organization.id == Membership.org_id)
                .where(Membership.user_id == user_id)
            )
        ).all()
    usable = [r for r in rows if r[3] == "active" and r[4] != "deleted"]
    usable.sort(key=lambda r: (r[4] != "active", _ROLE_RANK[Role(r[2])], r[5]))
    return [MeMembership(org_id=r[0], org_name=r[1], role=r[2]) for r in usable], bool(rows)


async def _session_for(user: User) -> AuthSession:
    memberships, had_any = await _workspaces(user.id)
    if not memberships and had_any and not user.is_superadmin:
        raise AppError(
            "account_disabled",
            "Your access to every workspace has been disabled. Contact your administrator.",
        )
    default = memberships[0] if memberships else None
    return AuthSession(
        user=AuthUser(id=user.id, email=str(user.email), name=user.name),
        org_id=default.org_id if default else NO_ORG,
        role=default.role if default else None,
        is_superadmin=user.is_superadmin,
        memberships=memberships,
        needs_onboarding=not memberships and not user.is_superadmin,
        must_change_password=user.must_change_password,
        home=home_for(default.role) if default else PORTAL_HOME[PORTAL_WORK],
    )


async def _authenticate(body: LoginIn, *, platform: bool) -> User:
    """Verify email + password for ONE portal. Customer sign-in and the platform (superadmin)
    sign-in are disjoint: a wrong-portal account fails exactly like a wrong password."""
    email = _normalize_email(body.email)
    now = utcnow()

    async with admin_session() as s:
        user = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is not None and user.locked_until is not None and user.locked_until > now:
            retry = int((user.locked_until - now).total_seconds()) + 1
            raise AppError(
                "account_locked",
                details={"retry_after_seconds": retry},
                headers={"Retry-After": str(retry)},
            )
        user_id = user.id if user is not None else None
        stored = user.password_hash if user is not None else None

    ok = await verify_password_async(body.password, stored)

    async with admin_session() as s:
        user = await s.get(User, user_id) if user_id is not None else None
        if user is not None and ok and user.is_superadmin != platform:
            ok = False  # right password, wrong portal
        if user is None or not ok:
            if user is not None:
                user.failed_login_count += 1
                if user.failed_login_count >= MAX_FAILED_ATTEMPTS:
                    user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
                    user.failed_login_count = 0
                    log.warning("login_locked", user_id=str(user.id))
            failed = True
        else:
            user.failed_login_count = 0
            user.locked_until = None
            user.last_login_at = now
            failed = False
    if failed:  # raised after the counter update is committed
        raise AppError("invalid_credentials")
    assert user is not None
    return user


async def login(body: LoginIn) -> AuthSession:
    """Customer portal sign-in (Owner, Admin, Manager, Member, Viewer)."""
    return await _session_for(await _authenticate(body, platform=False))


async def admin_login(body: LoginIn) -> AuthSession:
    """Platform Admin sign-in: superadmins only, no workspace, no customer memberships."""
    user = await _authenticate(body, platform=True)
    return AuthSession(
        user=AuthUser(id=user.id, email=str(user.email), name=user.name),
        org_id=NO_ORG,
        role=None,
        is_superadmin=True,
        memberships=[],
        needs_onboarding=False,
    )


async def signup(body: SignupIn) -> AuthSession:
    email = _normalize_email(str(body.email))
    password_hash = await hash_password_async(body.password)
    user = User(
        id=new_id(),
        email=email,
        name=body.name.strip(),
        password_hash=password_hash,
        last_login_at=utcnow(),
    )
    try:
        async with admin_session() as s:
            existing = (
                await s.execute(select(User.id).where(User.email == email))
            ).scalar_one_or_none()
            if existing is not None:
                raise AppError("conflict", "An account with this email already exists")
            s.add(user)
    except IntegrityError as e:  # concurrent signup with the same email
        raise AppError("conflict", "An account with this email already exists") from e
    return await _session_for(user)


def generate_temporary_password() -> str:
    """16 random url-safe characters; always satisfies the 10+ character password policy."""
    return secrets.token_urlsafe(12)


async def issue_set_password_token(s: AsyncSession, user_id: UUID, created_by: UUID | None) -> str:
    """Create a single-use set-password link token (7 days) and return the raw token. Earlier
    unused tokens for the same user stop working."""
    now = utcnow()
    for old in (
        await s.execute(
            select(PasswordToken).where(
                PasswordToken.user_id == user_id, PasswordToken.used_at.is_(None)
            )
        )
    ).scalars():
        old.used_at = now
    raw = secrets.token_urlsafe(32)
    s.add(
        PasswordToken(
            id=new_id(),
            user_id=user_id,
            token_hash=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            expires_at=now + SET_PASSWORD_TTL,
            created_by=created_by,
        )
    )
    await s.flush()
    return raw


async def set_password(body: SetPasswordIn) -> Ack:
    """Redeem an emailed set-password link. Unknown, used and expired tokens are indistinguishable."""
    token_hash = hashlib.sha256(body.token.encode("utf-8")).hexdigest()
    password_hash = await hash_password_async(body.password)
    now = utcnow()
    async with admin_session() as s:
        row = (
            await s.execute(select(PasswordToken).where(PasswordToken.token_hash == token_hash))
        ).scalar_one_or_none()
        if row is None or row.used_at is not None or row.expires_at < now:
            raise AppError("bad_request", "This link is invalid or has expired")
        user = await s.get(User, row.user_id)
        if user is None:
            raise AppError("bad_request", "This link is invalid or has expired")
        row.used_at = now
        user.password_hash = password_hash
        user.must_change_password = False
        user.failed_login_count = 0
        user.locked_until = None
    return Ack(ok=True)


async def change_password(user_id: UUID, body: ChangePasswordIn) -> Ack:
    """Signed-in user changes their own password (also clears a temporary-password flag)."""
    if body.new_password == body.current_password:
        raise AppError("bad_request", "Choose a password you have not used before")
    async with admin_session() as s:
        user = await s.get(User, user_id)
        stored = user.password_hash if user is not None else None
    if user is None or not await verify_password_async(body.current_password, stored):
        raise AppError("bad_request", "Your current password is incorrect")
    new_hash = await hash_password_async(body.new_password)
    async with admin_session() as s:
        user = await s.get(User, user_id)
        if user is None:
            raise AppError("not_found", "User not found")
        user.password_hash = new_hash
        user.must_change_password = False
    return Ack(ok=True)
