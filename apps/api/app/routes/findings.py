from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query

from app.contract import endpoint
from app.permissions import Action
from app.schemas.accounts import (
    DismissIn,
    FeedbackIn,
    FindingDetail,
    FindingListItem,
    FindingStatus,
    FindingType,
    Severity,
    SnoozeIn,
)
from app.schemas.identity import Ack
from app.utils.pagination import Page, PageParams, page_params

PAGE = "C2 Finding Detail"
Paging = Annotated[PageParams, Depends(page_params)]


@endpoint("GET", "/findings", group="findings", page=PAGE, owner="R", phase=3)
async def list_findings(
    page: Paging,
    status: Annotated[FindingStatus | None, Query()] = None,
    type: Annotated[FindingType | None, Query()] = None,
    severity: Annotated[Severity | None, Query()] = None,
    account_id: Annotated[UUID | None, Query()] = None,
) -> Page[FindingListItem]:
    """Findings list with filters."""
    raise NotImplementedError


@endpoint("GET", "/findings/{finding_id}", group="findings", page=PAGE, owner="R", phase=3)
async def get_finding(finding_id: UUID) -> FindingDetail:
    """Full finding: claims, evidence, unknowns, contradictions, cards, history."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/findings/{finding_id}/dismiss",
    group="findings",
    page=PAGE,
    owner="R",
    phase=3,
    access=Action.APPROVE_OWN,
)
async def dismiss_finding(finding_id: UUID, body: DismissIn) -> FindingDetail:
    """Dismiss a finding with a reason (member: own accounts)."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/findings/{finding_id}/snooze",
    group="findings",
    page=PAGE,
    owner="R",
    phase=3,
    access=Action.APPROVE_OWN,
)
async def snooze_finding(finding_id: UUID, body: SnoozeIn) -> FindingDetail:
    """Snooze a finding until a date."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/findings/{finding_id}/reopen",
    group="findings",
    page=PAGE,
    owner="R",
    phase=3,
    access=Action.APPROVE_OWN,
)
async def reopen_finding(finding_id: UUID) -> FindingDetail:
    """Reopen a dismissed or snoozed finding."""
    raise NotImplementedError


@endpoint(
    "POST", "/findings/{finding_id}/feedback", group="findings", page=PAGE, owner="R", phase=3
)
async def finding_feedback(finding_id: UUID, body: FeedbackIn) -> Ack:
    """Thumbs up/down on a finding."""
    raise NotImplementedError
