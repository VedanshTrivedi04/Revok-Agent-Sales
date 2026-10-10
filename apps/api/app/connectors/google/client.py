"""Google OAuth connector for Gmail and Google Calendar."""

from datetime import timedelta
from typing import Any, ClassVar
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.connectors.base import SyncResult, TokenSet
from app.connectors.ctx import ConnCtx
from app.utils.errors import AppError
from app.utils.time import utcnow

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

GCAL_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


class GoogleOAuthConnector:
    provider: ClassVar[str] = "google"

    def __init__(
        self,
        provider: str,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        scopes: list[str] | None = None,
    ) -> None:
        settings = get_settings()
        self.client_id = client_id or settings.google_client_id
        self.client_secret = client_secret or settings.google_client_secret
        if scopes:
            self.scopes = scopes
        elif provider == "gcal":
            self.scopes = GCAL_SCOPES
        else:
            self.scopes = GMAIL_SCOPES

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> TokenSet:
        payload = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data=payload)
            if resp.status_code != 200:
                raise AppError(
                    "integration_error",
                    f"Google code exchange failed with status {resp.status_code}",
                    status=400,
                )
            data = resp.json()
            expires_in = data.get("expires_in", 3600)
            return TokenSet(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                expires_at=utcnow() + timedelta(seconds=int(expires_in)),
                token_type=data.get("token_type", "Bearer"),
            )

    async def refresh(self, refresh_token: str) -> TokenSet:
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data=payload)
            if resp.status_code != 200:
                raise AppError(
                    "integration_needs_reauth",
                    f"Google token refresh failed with status {resp.status_code}",
                    status=401,
                )
            data = resp.json()
            expires_in = data.get("expires_in", 3600)
            return TokenSet(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token") or refresh_token,
                expires_at=utcnow() + timedelta(seconds=int(expires_in)),
                token_type=data.get("token_type", "Bearer"),
            )

    async def test_connection(self, ctx: ConnCtx) -> None:
        """Call Google userinfo endpoint to verify token."""
        await ctx.request("GET", "https://www.googleapis.com/oauth2/v2/userinfo")

    async def get_user_email(self, ctx: ConnCtx) -> str | None:
        resp: Any = await ctx.request("GET", "https://www.googleapis.com/oauth2/v2/userinfo")
        data = resp.json()
        email = data.get("email")
        return str(email) if email else None

    async def sync(
        self, ctx: ConnCtx, cursor: dict[str, Any], *, backfill_days: int | None
    ) -> SyncResult:
        await self.test_connection(ctx)
        return SyncResult(fetched=0, upserted=0, events_new=0, new_cursor=cursor, partial=False)


class GmailConnector(GoogleOAuthConnector):
    provider: ClassVar[str] = "gmail"

    def __init__(self, **kw: Any) -> None:
        super().__init__("gmail", **kw)


class GCalConnector(GoogleOAuthConnector):
    provider: ClassVar[str] = "gcal"

    def __init__(self, **kw: Any) -> None:
        super().__init__("gcal", **kw)
