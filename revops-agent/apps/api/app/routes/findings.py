from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Query, Request

from app.auth.deps import current_membership, get_claims
from app.contract import endpoint, real
from app.db.session import org_session
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
from app.services.findings import (
    dismiss_finding_service,
    finding_feedback_service,
    get_finding_detail_service,
    list_findings_service,
    reopen_finding_service,
    snooze_finding_service,
)
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


# ==============================================================================
# Real Handlers
# ==============================================================================


@real("list_findings")
async def list_findings_real(
    request: Request,
    page: PageParams,
    status: FindingStatus | None = None,
    type: FindingType | None = None,
    severity: Severity | None = None,
    account_id: UUID | None = None,
    **_: Any,
) -> Page[FindingListItem]:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await list_findings_service(
            s,
            org_id=m.org_id,
            page=page,
            status=status,
            type=type,
            severity=severity,
            account_id=account_id,
        )


@real("get_finding")
async def get_finding_real(request: Request, finding_id: UUID, **_: Any) -> FindingDetail:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await get_finding_detail_service(s, org_id=m.org_id, finding_id=finding_id)


@real("dismiss_finding")
async def dismiss_finding_real(
    request: Request, finding_id: UUID, body: DismissIn, **_: Any
) -> FindingDetail:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await dismiss_finding_service(
            s,
            org_id=m.org_id,
            user_id=m.user_id,
            user_role=m.role.value,
            finding_id=finding_id,
            body=body,
        )


@real("snooze_finding")
async def snooze_finding_real(
    request: Request, finding_id: UUID, body: SnoozeIn, **_: Any
) -> FindingDetail:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await snooze_finding_service(
            s,
            org_id=m.org_id,
            user_id=m.user_id,
            user_role=m.role.value,
            finding_id=finding_id,
            body=body,
        )


@real("reopen_finding")
async def reopen_finding_real(request: Request, finding_id: UUID, **_: Any) -> FindingDetail:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await reopen_finding_service(
            s,
            org_id=m.org_id,
            user_id=m.user_id,
            user_role=m.role.value,
            finding_id=finding_id,
        )


@real("finding_feedback")
async def finding_feedback_real(
    request: Request, finding_id: UUID, body: FeedbackIn, **_: Any
) -> Ack:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await finding_feedback_service(
            s,
            org_id=m.org_id,
            user_id=m.user_id,
            finding_id=finding_id,
            body=body,
        )
