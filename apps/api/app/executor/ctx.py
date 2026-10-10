"""Resolve the provider connection (ConnCtx) a card must execute or revert against.

CRM cards use the org's HubSpot integration. Email drafts and meeting requests are written into
the mailbox/calendar of the user who approved the card (user-level Google integration).
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.connectors.ctx import ConnCtx
from app.db.session import org_session
from app.models.integrations import Integration
from app.utils.errors import AppError

PROVIDER_FOR_TYPE = {
    "crm_task": "hubspot",
    "crm_note": "hubspot",
    "crm_field_update": "hubspot",
    "email_draft": "gmail",
    "meeting_request": "gcal",
}
USABLE_STATUSES = ("connected", "syncing", "partial", "error")


def needs_provider(card_type: str) -> bool:
    return card_type in PROVIDER_FOR_TYPE


async def load_card_ctx(org_id: UUID, card: Any) -> ConnCtx | None:
    """ConnCtx for the card's provider, or None for types without a provider (slack_internal).

    Raises AppError(integration_needs_reauth) when the integration is missing, disconnected or
    needs re-authorization: the user must reconnect before the card can run or be reverted.
    """
    provider = PROVIDER_FOR_TYPE.get(card.type)
    if provider is None:
        return None
    q = select(Integration).where(Integration.provider == provider)
    if provider in ("gmail", "gcal"):
        user_id = card.decided_by or card.assignee_user_id
        if user_id is None:
            raise AppError("integration_needs_reauth", "No user to act for on this card")
        q = q.where(Integration.user_id == user_id)
    else:
        q = q.where(Integration.scope_level == "org")
    async with org_session(org_id) as s:
        integ = (
            await s.execute(q.order_by(Integration.created_at.desc()).limit(1))
        ).scalar_one_or_none()
    if integ is None or integ.status not in USABLE_STATUSES:
        state = "not connected" if integ is None else integ.status
        raise AppError(
            "integration_needs_reauth",
            f"{provider} is {state}; reconnect it in Settings > Integrations",
            details={"provider": provider},
        )
    return await ConnCtx.load(org_id, integ.id)
