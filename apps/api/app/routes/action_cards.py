from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Query, Request

from app.auth.deps import current_membership, get_claims
from app.contract import endpoint, real
from app.db.session import org_session
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
from app.services import cards as cards_service
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


@real("list_cards")
async def list_cards_real(
    request: Request,
    page: PageParams,
    status: CardStatus | None = None,
    assignee: str | None = None,
    type: CardType | None = None,
    **_: Any,
) -> Page[CardOut]:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await cards_service.list_cards(
            s,
            org_id=m.org_id,
            user_id=m.user_id,
            user_role=m.role,
            status=status,
            assignee=assignee,
            card_type=type,
            page_params=page,
        )


@real("get_card")
async def get_card_real(request: Request, card_id: UUID, **_: Any) -> CardOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await cards_service.get_card(s, org_id=m.org_id, card_id=card_id)


@real("patch_card")
async def patch_card_real(request: Request, card_id: UUID, body: CardPatchIn, **_: Any) -> CardOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await cards_service.patch_card(
            s,
            org_id=m.org_id,
            user_id=m.user_id,
            user_role=m.role,
            card_id=card_id,
            patch_in=body,
        )


@real("approve_card")
async def approve_card_real(
    request: Request, card_id: UUID, body: CardApproveIn, **_: Any
) -> CardOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await cards_service.approve_card(
            s,
            org_id=m.org_id,
            user_id=m.user_id,
            user_role=m.role,
            card_id=card_id,
            approve_in=body,
            channel="web",
        )


@real("reject_card")
async def reject_card_real(
    request: Request, card_id: UUID, body: CardRejectIn, **_: Any
) -> CardOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await cards_service.reject_card(
            s,
            org_id=m.org_id,
            user_id=m.user_id,
            user_role=m.role,
            card_id=card_id,
            reject_in=body,
            channel="web",
        )


@real("assign_card")
async def assign_card_real(
    request: Request, card_id: UUID, body: CardAssignIn, **_: Any
) -> CardOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await cards_service.assign_card(
            s,
            org_id=m.org_id,
            user_id=m.user_id,
            user_role=m.role,
            card_id=card_id,
            assign_in=body,
        )


@real("retry_card")
async def retry_card_real(request: Request, card_id: UUID, **_: Any) -> CardOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await cards_service.retry_card(
            s,
            org_id=m.org_id,
            user_id=m.user_id,
            user_role=m.role,
            card_id=card_id,
        )


@real("revert_card")
async def revert_card_real(request: Request, card_id: UUID, **_: Any) -> CardOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        from app.executor.revert import revert_card

        return await revert_card(
            s,
            org_id=m.org_id,
            user_id=m.user_id,
            user_role=m.role,
            card_id=card_id,
            ctx=None,  # No live connector in template/test mode
        )
