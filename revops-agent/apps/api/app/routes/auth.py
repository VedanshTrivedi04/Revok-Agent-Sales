from typing import Any

from fastapi import Request

from app.auth.deps import get_claims
from app.contract import endpoint, real
from app.schemas.identity import (
    Ack,
    AuthSession,
    ChangePasswordIn,
    LoginIn,
    SetPasswordIn,
    SignupIn,
)
from app.services import auth as auth_service

PAGE = "A2 Sign in"


@endpoint("POST", "/auth/login", group="auth", page=PAGE, owner="V", phase=1, access="public")
async def login(body: LoginIn) -> AuthSession:
    """Email + password sign-in; returns the identity and default workspace for the session."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/auth/admin/login",
    group="auth",
    page="E0 Admin login",
    owner="V",
    phase=5,
    access="public",
)
async def admin_login(body: LoginIn) -> AuthSession:
    """Platform Admin (superadmin) sign-in; separate from the customer portal sign-in."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/auth/signup",
    group="auth",
    page="A3 Create account",
    owner="V",
    phase=1,
    access="public",
    status_code=201,
)
async def signup(body: SignupIn) -> AuthSession:
    """Create an account with email + password (workspace is created in onboarding)."""
    raise NotImplementedError


@real("login")
async def login_real(body: LoginIn, **_: Any) -> AuthSession:
    return await auth_service.login(body)


@real("signup")
async def signup_real(body: SignupIn, **_: Any) -> AuthSession:
    return await auth_service.signup(body)


@real("admin_login")
async def admin_login_real(body: LoginIn, **_: Any) -> AuthSession:
    return await auth_service.admin_login(body)


@endpoint(
    "POST", "/auth/set-password", group="auth", page="A6 Set password", owner="V", phase=6,
    access="public",
)  # fmt: skip
async def set_password(body: SetPasswordIn) -> Ack:
    """Choose a password from the emailed one-time link (client onboarding)."""
    raise NotImplementedError


@endpoint(
    "POST", "/auth/change-password", group="auth", page="A6 Set password", owner="V", phase=6,
    access="user",
)  # fmt: skip
async def change_password(body: ChangePasswordIn) -> Ack:
    """Change your own password; required after sign-in with a temporary password."""
    raise NotImplementedError


@real("set_password")
async def set_password_real(body: SetPasswordIn, **_: Any) -> Ack:
    return await auth_service.set_password(body)


@real("change_password")
async def change_password_real(request: Request, body: ChangePasswordIn, **_: Any) -> Ack:
    claims = get_claims(request)
    return await auth_service.change_password(claims.user_id, body)
