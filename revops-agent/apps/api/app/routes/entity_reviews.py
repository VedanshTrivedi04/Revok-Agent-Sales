from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app.auth.deps import CurrentMembership
from app.contract import endpoint, real
from app.db.session import org_session
from app.permissions import Action
from app.schemas.identity import Ack
from app.schemas.ops import EntityReviewOut, EntityReviewResolveIn
from app.services.entity_reviews import (
    list_entity_reviews_service,
    resolve_entity_review_service,
)
from app.utils.pagination import Page, PageParams, page_params

PAGE = "C9 Entity Review"


@endpoint(
    "GET",
    "/entity-reviews",
    group="entity_reviews",
    page=PAGE,
    owner="R",
    phase=2,
    access=Action.VIEW_ENTITY_REVIEW,
)
async def list_entity_reviews(
    page: Annotated[PageParams, Depends(page_params)],
) -> Page[EntityReviewOut]:
    """Ambiguous email/account matches waiting for a human."""
    raise NotImplementedError


@real("list_entity_reviews")
async def list_entity_reviews_real(
    membership: CurrentMembership,
    page: Annotated[PageParams, Depends(page_params)],
) -> Page[EntityReviewOut]:
    async with org_session(membership.org_id) as session:
        return await list_entity_reviews_service(session, membership.org_id, page)


@endpoint(
    "POST",
    "/entity-reviews/{review_id}/resolve",
    group="entity_reviews",
    page=PAGE,
    owner="R",
    phase=2,
    access=Action.VIEW_ENTITY_REVIEW,
)
async def resolve_entity_review(review_id: UUID, body: EntityReviewResolveIn) -> Ack:
    """Assign the event to an account, or ignore it."""
    raise NotImplementedError


@real("resolve_entity_review")
async def resolve_entity_review_real(
    review_id: UUID,
    body: EntityReviewResolveIn,
    membership: CurrentMembership,
) -> Ack:
    async with org_session(membership.org_id) as session:
        return await resolve_entity_review_service(
            session, membership.org_id, membership.user_id, review_id, body
        )
