from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query

from app.contract import endpoint
from app.permissions import Action
from app.schemas.cards import (
    CardApproveIn,
    CardAssignIn,
    CardOut,
    CardPatchIn,
    CardRejectIn,
    CardStatus,
    CardType,
)
from app.utils.pagination import Page, PageParams, page_params

PAGE = "C3 Approval Inbox"
Paging = Annotated[PageParams, Depends(page_params)]


@endpoint("GET", "/action-cards", group="action_cards", page=PAGE, owner="V", phase=2)
async def list_cards(
    page: Paging,
    status: Annotated[CardStatus | None, Query()] = None,
    assignee: Annotated[str | None, Query(description="me | <user_id>")] = None,
    type: Annotated[CardType | None, Query()] = None,
) -> Page[CardOut]:
    """Approval inbox."""
    raise NotImplementedError


@endpoint(
    "GET",
    "/action-cards/{card_id}",
    group="action_cards",
    page="C4 Action Card",
    owner="V",
    phase=2,
)
async def get_card(card_id: UUID) -> CardOut:
    """One action card."""
    raise NotImplementedError


@endpoint(
    "PATCH",
    "/action-cards/{card_id}",
    group="action_cards",
    page="C4 Action Card",
    owner="V",
    phase=2,
    access=Action.EDIT_CARD,
)
async def patch_card(card_id: UUID, body: CardPatchIn) -> CardOut:
    """Save edits (validated against the type schema and allowlists)."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/action-cards/{card_id}/approve",
    group="action_cards",
    page="C4 Action Card",
    owner="V",
    phase=2,
    access=Action.APPROVE_OWN,
    status_code=202,
)
async def approve_card(card_id: UUID, body: CardApproveIn) -> CardOut:
    """Approve (optionally with edits) and enqueue execution."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/action-cards/{card_id}/reject",
    group="action_cards",
    page="C4 Action Card",
    owner="V",
    phase=2,
    access=Action.APPROVE_OWN,
)
async def reject_card(card_id: UUID, body: CardRejectIn) -> CardOut:
    """Reject with a reason."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/action-cards/{card_id}/assign",
    group="action_cards",
    page="C4 Action Card",
    owner="V",
    phase=2,
    access=Action.APPROVE_OWN,
)
async def assign_card(card_id: UUID, body: CardAssignIn) -> CardOut:
    """Reassign a card to another member."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/action-cards/{card_id}/revert",
    group="action_cards",
    page="C4 Action Card",
    owner="V",
    phase=3,
    access=Action.REVERT,
)
async def revert_card(card_id: UUID) -> CardOut:
    """Revert an executed action (409 revert_conflict if the value changed)."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/action-cards/{card_id}/retry",
    group="action_cards",
    page="C4 Action Card",
    owner="V",
    phase=3,
    access=Action.APPROVE_ANY,
    status_code=202,
)
async def retry_card(card_id: UUID) -> CardOut:
    """Retry a failed card (manager+)."""
    raise NotImplementedError
