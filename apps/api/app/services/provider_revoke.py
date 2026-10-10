"""Best-effort token revocation at the provider when an integration is disconnected or an org is
deleted. Never raises, never logs tokens; local tokens are wiped by the caller regardless."""

from uuid import UUID

import httpx
import structlog

from app.connectors.ctx import ConnCtx

log = structlog.get_logger()
TIMEOUT = 5.0


async def revoke_provider_tokens(org_id: UUID, integration_id: UUID, provider: str) -> bool:
    """True when the provider acknowledged the revocation."""
    try:
        access, refresh, _ = await ConnCtx(org_id, integration_id, provider)._read()
    except Exception:
        return False  # nothing stored or undecryptable: nothing to revoke
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            if provider in ("gmail", "gcal"):
                resp = await client.post(
                    "https://oauth2.googleapis.com/revoke", data={"token": refresh or access}
                )
            elif provider == "slack":
                resp = await client.post(
                    "https://slack.com/api/auth.revoke",
                    headers={"Authorization": f"Bearer {access}"},
                )
            elif provider == "hubspot" and refresh:
                resp = await client.delete(
                    f"https://api.hubapi.com/oauth/v1/refresh-tokens/{refresh}"
                )
            else:
                return False
        return resp.status_code < 400
    except Exception as exc:
        log.warning("provider_revoke_failed", provider=provider, error=type(exc).__name__)
        return False
