from typing import Any

from fastapi import Body
from fastapi.responses import RedirectResponse

from app.contract import endpoint
from app.schemas.integrations import SlackAck

PAGE = "F Slack"


@endpoint("POST", "/slack/events", group="slack", page=PAGE, owner="V", phase=4, access="public")
async def slack_events(payload: dict[str, Any] = Body(...)) -> SlackAck:
    """Slack Events API (URL verification + events). Signature-verified; must ack within 3 s."""
    raise NotImplementedError


@endpoint(
    "POST", "/slack/interactions", group="slack", page=PAGE, owner="V", phase=4, access="public"
)
async def slack_interactions(payload: dict[str, Any] = Body(...)) -> SlackAck:
    """Slack block actions and view submissions. Signature-verified; must ack within 3 s."""
    raise NotImplementedError


@endpoint(
    "GET",
    "/slack/oauth/callback",
    group="slack",
    page="B6 Slack",
    owner="V",
    phase=4,
    access="public",
    status_code=302,
    response_class=RedirectResponse,
)
async def slack_oauth_callback(code: str, state: str) -> RedirectResponse:
    """Slack OAuth v2 redirect target."""
    raise NotImplementedError
