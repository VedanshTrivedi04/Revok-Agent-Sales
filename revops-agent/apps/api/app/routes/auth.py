from typing import Any

from app.contract import endpoint, real
from app.schemas.identity import AuthSession, LoginIn, SignupIn
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
