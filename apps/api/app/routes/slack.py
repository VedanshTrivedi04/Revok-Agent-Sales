import json
import time
from typing import Any
from uuid import UUID

from fastapi import Body, Request
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.contract import endpoint, real
from app.schemas.integrations import SlackAck
from app.services.slack import (
    handle_slack_oauth_callback,
    is_duplicate_interaction,
    resolve_org_from_slack_payload,
    verify_slack_signature,
)
from app.utils.errors import AppError
from app.workers.tasks_slack import process_slack_interaction_task

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


# ============================================================ Real Handlers


async def _verify_request(request: Request, raw_body: bytes) -> None:
    settings = get_settings()
    secret = settings.slack_signing_secret
    sig = request.headers.get("x-slack-signature", "")
    ts = request.headers.get("x-slack-request-timestamp", "")

    # In strict mode with secret configured, or if signature header is provided:
    if secret or sig:
        if not verify_slack_signature(secret, ts, raw_body, sig):
            raise AppError("forbidden", "Invalid Slack signature")


@real("slack_events")
async def slack_events_real(
    request: Request, payload: dict[str, Any] | None = None, **_: Any
) -> SlackAck:
    raw_body = await request.body()
    await _verify_request(request, raw_body)

    if payload is None:
        try:
            payload = json.loads(raw_body)
        except Exception:
            payload = {}

    if payload.get("type") == "url_verification":
        return SlackAck(ok=True, challenge=payload.get("challenge"))

    return SlackAck(ok=True)


@real("slack_interactions")
async def slack_interactions_real(
    request: Request, payload: dict[str, Any] | None = None, **_: Any
) -> SlackAck:
    raw_body = await request.body()
    await _verify_request(request, raw_body)

    # Slack interactions may be submitted as multipart/x-www-form-urlencoded or JSON
    if payload is None or not payload:
        try:
            form = await request.form()
            if "payload" in form:
                payload = json.loads(str(form["payload"]))
            else:
                payload = json.loads(raw_body.decode())
        except Exception:
            if raw_body:
                try:
                    payload = json.loads(raw_body.decode())
                except Exception:
                    payload = {}
            else:
                payload = {}

    # Deduplication check: Redis SETNX slack:{action_ts}:{user} TTL 1h
    actions = payload.get("actions", [])
    action = actions[0] if actions else {}
    action_ts = str(
        action.get("action_ts")
        or payload.get("action_ts")
        or payload.get("trigger_id")
        or time.time()
    )
    user_id = str(payload.get("user", {}).get("id") or "unknown_user")

    if await is_duplicate_interaction(action_ts, user_id):
        # Already processed, ACK immediately without re-executing
        return SlackAck(ok=True, extra={"deduped": True})

    # Resolve org and dispatch async task to notify queue
    org_id = await resolve_org_from_slack_payload(payload)
    if org_id:
        process_slack_interaction_task.delay(str(org_id), payload)

    # Immediate ACK within 3 seconds
    return SlackAck(ok=True)


@real("slack_oauth_callback")
async def slack_oauth_callback_real(
    request: Request, code: str, state: str, **_: Any
) -> RedirectResponse:
    return await handle_slack_oauth_callback(code, state)
