"""Executor handler for `slack_internal` cards: post an internal message (DM or channel)."""

from typing import Any

from pydantic import BaseModel

from app.connectors.base import ExecResult
from app.connectors.slack.client import SlackConnector
from app.schemas.action_payloads import CrmRef
from app.utils.errors import FatalError, TransientError


class SlackInternalHandler:
    """Slack has no cheap lookup of a posted message, so provider-side idempotency relies on the
    executor's exec:{card} lock and the approved->executing transition (a card runs once)."""

    provider = "slack"

    async def find_existing(self, ctx: Any, idem_key: str) -> ExecResult | None:
        return None

    async def apply(
        self, ctx: Any, action_type: str, payload: BaseModel, idem_key: str
    ) -> ExecResult:
        from app.services.slack import get_slack_bot_token

        token = await get_slack_bot_token(ctx.org_id)
        if not token:
            raise FatalError("Slack is not connected for this organization")
        target = getattr(payload, "target", "")
        if not target:
            raise FatalError("Slack target is empty (owner has no linked Slack user)")
        resp = await SlackConnector().chat_post_message(token, target, getattr(payload, "text", ""))
        if not resp.get("ok"):
            error = str(resp.get("error", "unknown"))
            if error in ("ratelimited", "internal_error", "service_unavailable"):
                raise TransientError(f"Slack temporarily unavailable: {error}")
            raise FatalError(f"Slack rejected the message: {error}")
        return ExecResult(
            external_ref={"slack_ts": resp.get("ts"), "slack_channel": resp.get("channel")}
        )

    async def read_current(self, ctx: Any, ref: CrmRef, fields: list[str]) -> dict[str, Any]:
        return {}


slack_internal_handler = SlackInternalHandler()
