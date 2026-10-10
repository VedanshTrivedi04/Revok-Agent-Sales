"""HubSpot API client and OAuth connector.

Implements `OAuthConnector`:
  - OAuth authorization URL, code exchange, and token refresh.
  - Connection test via account info / token info endpoint.
  - Owners list (email -> owner_id mapping).
  - Properties listing by object type (companies, deals, contacts).
  - Object search and paging with `after` cursor.
"""

from datetime import timedelta
from typing import Any, ClassVar
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel

from app.config import get_settings
from app.connectors.base import OAuthConnector, SyncResult, TokenSet
from app.connectors.ctx import ConnCtx
from app.utils.errors import AppError
from app.utils.time import utcnow

HUBSPOT_AUTH_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
HUBSPOT_BASE_URL = "https://api.hubapi.com"

DEFAULT_SCOPES = [
    "crm.objects.contacts.read",
    "crm.objects.contacts.write",
    "crm.objects.companies.read",
    "crm.objects.companies.write",
    "crm.objects.deals.read",
    "crm.objects.deals.write",
    "crm.objects.owners.read",
    "crm.schemas.companies.read",
    "crm.schemas.deals.read",
    "crm.schemas.contacts.read",
]


class HubSpotAccountInfo(BaseModel):
    portal_id: str
    account_name: str | None = None
    time_zone: str | None = None
    currency: str | None = None


class HubSpotOwner(BaseModel):
    id: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    user_id: int | None = None


class HubSpotProperty(BaseModel):
    name: str
    label: str
    type: str
    field_type: str | None = None
    group_name: str | None = None
    options: list[dict[str, Any]] = []


class HubSpotConnector(OAuthConnector):
    provider: ClassVar[str] = "hubspot"

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        scopes: list[str] | None = None,
    ) -> None:
        settings = get_settings()
        self.client_id = client_id or settings.hubspot_client_id
        self.client_secret = client_secret or settings.hubspot_client_secret
        self.scopes = scopes or DEFAULT_SCOPES

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(self.scopes),
            "state": state,
        }
        return f"{HUBSPOT_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> TokenSet:
        payload = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(HUBSPOT_TOKEN_URL, data=payload)
            if resp.status_code != 200:
                raise AppError(
                    "integration_error",
                    f"HubSpot code exchange failed with status {resp.status_code}",
                    status=400,
                )
            data = resp.json()
            expires_in = data.get("expires_in", 1800)
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
            resp = await client.post(HUBSPOT_TOKEN_URL, data=payload)
            if resp.status_code != 200:
                raise AppError(
                    "integration_needs_reauth",
                    f"HubSpot token refresh failed with status {resp.status_code}",
                    status=401,
                )
            data = resp.json()
            expires_in = data.get("expires_in", 1800)
            return TokenSet(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token") or refresh_token,
                expires_at=utcnow() + timedelta(seconds=int(expires_in)),
                token_type=data.get("token_type", "Bearer"),
            )

    async def test_connection(self, ctx: ConnCtx) -> None:
        """Verify token works and endpoint returns portal info."""
        await self.get_account_info(ctx)

    async def get_account_info(self, ctx: ConnCtx) -> HubSpotAccountInfo:
        resp: Any = await ctx.request("GET", "/account-info/v3/details")
        data = resp.json()
        portal_id = str(data.get("portalId", data.get("portal_id", "")))
        name = data.get("accountType") or f"Portal {portal_id}"
        return HubSpotAccountInfo(
            portal_id=portal_id,
            account_name=name,
            time_zone=data.get("timeZone"),
            currency=data.get("currency"),
        )

    async def get_owners(self, ctx: ConnCtx) -> list[HubSpotOwner]:
        resp: Any = await ctx.request("GET", "/crm/v3/owners")
        data = resp.json()
        results = data.get("results", [])
        return [
            HubSpotOwner(
                id=str(r.get("id")),
                email=r.get("email"),
                first_name=r.get("firstName"),
                last_name=r.get("lastName"),
                user_id=r.get("userId"),
            )
            for r in results
        ]

    async def get_properties(self, ctx: ConnCtx, object_type: str) -> list[HubSpotProperty]:
        resp: Any = await ctx.request("GET", f"/crm/v3/properties/{object_type}")
        data = resp.json()
        results = data.get("results", [])
        return [
            HubSpotProperty(
                name=r.get("name", ""),
                label=r.get("label", ""),
                type=r.get("type", "string"),
                field_type=r.get("fieldType"),
                group_name=r.get("groupName"),
                options=r.get("options", []),
            )
            for r in results
        ]

    async def search_objects(
        self,
        ctx: ConnCtx,
        object_type: str,
        *,
        properties: list[str] | None = None,
        after: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if properties:
            params["properties"] = ",".join(properties)
        if after:
            params["after"] = after
        query = urlencode(params)
        resp: Any = await ctx.request("GET", f"/crm/v3/objects/{object_type}?{query}")
        result: dict[str, Any] = resp.json()
        return result

    async def sync(
        self, ctx: ConnCtx, cursor: dict[str, Any], *, backfill_days: int | None
    ) -> SyncResult:
        # Full sync is Phase 2 (R2-01); here test_connection is verified
        await self.test_connection(ctx)
        return SyncResult(fetched=0, upserted=0, events_new=0, new_cursor=cursor, partial=False)
