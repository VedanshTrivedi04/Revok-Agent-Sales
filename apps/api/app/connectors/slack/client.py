"""Slack connector implementation via Web API and OAuth v2.

Implements OAuthConnector protocol with scopes:
  chat:write, im:write, users:read, users:read.email, channels:read
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx
import structlog

from app.config import get_settings
from app.connectors.base import OAuthConnector, SyncResult, TokenSet
from app.connectors.ctx import ConnCtx
from app.utils.errors import AppError

log = structlog.get_logger()

SLACK_API_BASE = "https://slack.com/api"
SLACK_SCOPES = [
    "chat:write",
    "im:write",
    "users:read",
    "users:read.email",
    "channels:read",
]


class SlackConnector(OAuthConnector):
    """Slack OAuth v2 connector."""

    provider = "slack"

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        settings = get_settings()
        client_id = settings.slack_client_id or "mock-slack-client-id"
        params = {
            "client_id": client_id,
            "scope": ",".join(SLACK_SCOPES),
            "state": state,
            "redirect_uri": redirect_uri,
        }
        return f"https://slack.com/oauth/v2/authorize?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> TokenSet:
        settings = get_settings()
        client_id = settings.slack_client_id or "mock-slack-client-id"
        client_secret = settings.slack_client_secret or "mock-slack-client-secret"

        # Mock API / testing fallback
        if settings.mock_api or code.startswith("mock_"):
            return TokenSet(
                access_token=f"xoxb-mock-token-{code}",
                refresh_token=None,
                token_type="Bearer",
                raw={"team": {"id": "T_MOCK_TEAM", "name": "Mock Workspace"}},
            )

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{SLACK_API_BASE}/oauth.v2.access",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                timeout=10.0,
            )

        if resp.status_code != 200:
            raise AppError("bad_gateway", f"Slack OAuth failed with HTTP {resp.status_code}")

        data = resp.json()
        if not data.get("ok"):
            error = data.get("error", "unknown_error")
            raise AppError("oauth_failed", f"Slack OAuth error: {error}")

        # The bot token starts with xoxb-
        bot_token = data.get("access_token", "")
        return TokenSet(
            access_token=bot_token,
            refresh_token=None,
            token_type="Bearer",
            raw=data,
        )

    async def refresh(self, refresh_token: str) -> TokenSet:
        # Slack bot tokens do not rotate by default
        return TokenSet(access_token=refresh_token)

    async def test_connection(self, ctx: ConnCtx) -> None:
        token = await ctx.access_token()
        if not token:
            raise AppError("unauthenticated", "No access token available for Slack")

    async def sync(
        self, ctx: ConnCtx, cursor: dict[str, Any], *, backfill_days: int | None
    ) -> SyncResult:
        # Slack does not run sync cycles for telemetry
        return SyncResult(fetched=0, upserted=0, events_new=0, new_cursor=cursor)

    # -----------------------------------------------------------------------
    # Slack Web API Client Methods
    # -----------------------------------------------------------------------

    async def users_list(self, token: str) -> list[dict[str, Any]]:
        """Fetch workspace users list from Slack."""
        settings = get_settings()
        if settings.mock_api or token.startswith("xoxb-mock"):
            return [
                {
                    "id": "U12345678",
                    "name": "alice",
                    "real_name": "Alice Lead",
                    "profile": {"email": "lead@acme.com"},
                    "is_bot": False,
                    "deleted": False,
                },
                {
                    "id": "U87654321",
                    "name": "bob",
                    "real_name": "Bob Manager",
                    "profile": {"email": "bob@example.com"},
                    "is_bot": False,
                    "deleted": False,
                },
            ]

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{SLACK_API_BASE}/users.list",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )

        if resp.status_code != 200:
            log.error("slack_users_list_failed", status=resp.status_code)
            return []

        data = resp.json()
        if not data.get("ok"):
            log.error("slack_users_list_error", error=data.get("error"))
            return []

        members: list[dict[str, Any]] = data.get("members", [])
        return [m for m in members if not m.get("is_bot") and not m.get("deleted")]

    async def chat_post_message(
        self,
        token: str,
        channel: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Post a chat message to a Slack channel or DM."""
        settings = get_settings()
        if settings.mock_api or token.startswith("xoxb-mock"):
            return {"ok": True, "ts": "1234567890.123456", "channel": channel}

        payload: dict[str, Any] = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{SLACK_API_BASE}/chat.postMessage",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
                timeout=10.0,
            )

        return resp.json() if resp.status_code == 200 else {"ok": False}

    async def chat_update(
        self,
        token: str,
        channel: str,
        ts: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Update an existing chat message."""
        settings = get_settings()
        if settings.mock_api or token.startswith("xoxb-mock"):
            return {"ok": True, "ts": ts, "channel": channel}

        payload: dict[str, Any] = {"channel": channel, "ts": ts, "text": text}
        if blocks:
            payload["blocks"] = blocks

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{SLACK_API_BASE}/chat.update",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
                timeout=10.0,
            )

        return resp.json() if resp.status_code == 200 else {"ok": False}

    async def post_response_url(
        self,
        response_url: str,
        payload: dict[str, Any],
    ) -> bool:
        """Post back to Slack using interaction response_url."""
        if not response_url or response_url.startswith("http://mock"):
            return True

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                response_url,
                json=payload,
                timeout=10.0,
            )
            return resp.status_code == 200
