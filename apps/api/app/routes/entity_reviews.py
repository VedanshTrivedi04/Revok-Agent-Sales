from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app.contract import endpoint
from app.permissions import Action
from app.schemas.identity import Ack
from app.schemas.ops import EntityReviewOut, EntityReviewResolveIn
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
