from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import Depends, Query, Request

from app.auth.deps import CurrentMembership, current_membership, get_claims
from app.contract import endpoint, real
from app.db.session import org_session
from app.permissions import Action
from app.schemas.accounts import (
    AccountDetail,
    AccountListItem,
    AccountPatchIn,
    ContactOut,
    DealOut,
    RunTriggerOut,
    TimelineEvent,
    TodayResponse,
    UsageSeries,
)
from app.services.accounts import (
    get_account_detail_service,
    get_account_timeline_service,
    get_account_usage_service,
    list_account_contacts_service,
    list_account_deals_service,
    list_accounts_service,
    patch_account_service,
    run_account_service,
)
from app.services.findings import get_today_service
from app.utils.pagination import Page, PageParams, page_params

Paging = Annotated[PageParams, Depends(page_params)]


@endpoint("GET", "/today", group="today", page="C1 Today", owner="R", phase=3)
async def get_today(
    type: Annotated[Literal["risk", "expansion", "all"], Query()] = "all",
    owner: Annotated[str | None, Query(description="me | all | <user_id>")] = None,
    severity: Annotated[Literal["high", "medium", "low"] | None, Query()] = None,
    renewal_within: Annotated[int | None, Query(ge=1, le=365)] = None,
) -> TodayResponse:
    """Ranked open findings with account summary and pending card counts."""
    raise NotImplementedError


@real("get_today")
async def get_today_real(
    request: Request,
    type: Literal["risk", "expansion", "all"] = "all",
    owner: str | None = None,
    severity: Literal["high", "medium", "low"] | None = None,
    renewal_within: int | None = None,
    **_: Any,
) -> TodayResponse:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as session:
        return await get_today_service(
            session,
            org_id=m.org_id,
            current_user_id=m.user_id,
            current_user_role=m.role.value,
            type=type,
            owner=owner,
            severity=severity,
            renewal_within=renewal_within,
        )


@endpoint("GET", "/accounts", group="accounts", page="C5 Accounts", owner="R", phase=2)
async def list_accounts(
    page: Paging,
    query: Annotated[str | None, Query()] = None,
    owner: Annotated[str | None, Query()] = None,
    risk: Annotated[Literal["high", "medium", "low"] | None, Query()] = None,
    renewal_within: Annotated[int | None, Query(ge=1, le=365)] = None,
    sort: Annotated[Literal["priority", "arr", "renewal", "name"], Query()] = "priority",
) -> Page[AccountListItem]:
    """Accounts list with filters and sorting."""
    raise NotImplementedError


@real("list_accounts")
async def list_accounts_real(
    membership: CurrentMembership,
    page: Paging,
    query: Annotated[str | None, Query()] = None,
    owner: Annotated[str | None, Query()] = None,
    risk: Annotated[Literal["high", "medium", "low"] | None, Query()] = None,
    renewal_within: Annotated[int | None, Query(ge=1, le=365)] = None,
    sort: Annotated[Literal["priority", "arr", "renewal", "name"], Query()] = "priority",
) -> Page[AccountListItem]:
    async with org_session(membership.org_id) as session:
        return await list_accounts_service(
            session,
            membership.org_id,
            page,
            query=query,
            owner=owner,
            current_user_id=membership.user_id,
            risk=risk,
            renewal_within=renewal_within,
            sort=sort,
        )


@endpoint(
    "GET", "/accounts/{account_id}", group="accounts", page="C6 Account Detail", owner="R", phase=2
)
async def get_account(account_id: UUID) -> AccountDetail:
    """Account detail with metrics and open findings."""
    raise NotImplementedError


@real("get_account")
async def get_account_real(
    account_id: UUID,
    membership: CurrentMembership,
) -> AccountDetail:
    async with org_session(membership.org_id) as session:
        return await get_account_detail_service(session, membership.org_id, account_id)


@endpoint(
    "GET",
    "/accounts/{account_id}/timeline",
    group="accounts",
    page="C6 Account Detail",
    owner="R",
    phase=2,
)
async def get_account_timeline(
    account_id: UUID,
    page: Paging,
    types: Annotated[str | None, Query(description="comma-separated event types")] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
) -> Page[TimelineEvent]:
    """Account timeline events."""
    raise NotImplementedError


@real("get_account_timeline")
async def get_account_timeline_real(
    account_id: UUID,
    page: Paging,
    membership: CurrentMembership,
    types: Annotated[str | None, Query(description="comma-separated event types")] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
) -> Page[TimelineEvent]:
    async with org_session(membership.org_id) as session:
        return await get_account_timeline_service(
            session, membership.org_id, account_id, page, types=types, from_=from_, to=to
        )


@endpoint(
    "GET",
    "/accounts/{account_id}/usage",
    group="accounts",
    page="C6 Account Detail",
    owner="R",
    phase=2,
)
async def get_account_usage(
    account_id: UUID,
    granularity: Annotated[Literal["day", "week"], Query()] = "week",
    weeks: Annotated[int, Query(ge=1, le=52)] = 12,
) -> UsageSeries:
    """Usage series for charts."""
    raise NotImplementedError


@real("get_account_usage")
async def get_account_usage_real(
    account_id: UUID,
    membership: CurrentMembership,
    granularity: Annotated[Literal["day", "week"], Query()] = "week",
    weeks: Annotated[int, Query(ge=1, le=52)] = 12,
) -> UsageSeries:
    async with org_session(membership.org_id) as session:
        return await get_account_usage_service(
            session, membership.org_id, account_id, granularity=granularity, weeks=weeks
        )


@endpoint(
    "GET",
    "/accounts/{account_id}/contacts",
    group="accounts",
    page="C6 Account Detail",
    owner="R",
    phase=2,
)
async def list_account_contacts(account_id: UUID) -> list[ContactOut]:
    """Account contacts."""
    raise NotImplementedError


@real("list_account_contacts")
async def list_account_contacts_real(
    account_id: UUID,
    membership: CurrentMembership,
) -> list[ContactOut]:
    async with org_session(membership.org_id) as session:
        return await list_account_contacts_service(session, membership.org_id, account_id)


@endpoint(
    "GET",
    "/accounts/{account_id}/deals",
    group="accounts",
    page="C6 Account Detail",
    owner="R",
    phase=2,
)
async def list_account_deals(account_id: UUID) -> list[DealOut]:
    """Account deals."""
    raise NotImplementedError


@real("list_account_deals")
async def list_account_deals_real(
    account_id: UUID,
    membership: CurrentMembership,
) -> list[DealOut]:
    async with org_session(membership.org_id) as session:
        return await list_account_deals_service(session, membership.org_id, account_id)


@endpoint(
    "POST",
    "/accounts/{account_id}/run",
    group="accounts",
    page="C6 Account Detail",
    owner="R",
    phase=3,
    access=Action.RUN_NOW,
    status_code=202,
)
async def run_account(account_id: UUID) -> RunTriggerOut:
    """Enqueue a manual agent run for the account (member: own accounts only)."""
    raise NotImplementedError


@real("run_account")
async def run_account_real(
    account_id: UUID,
    membership: CurrentMembership,
) -> RunTriggerOut:
    async with org_session(membership.org_id) as session:
        return await run_account_service(session, membership.org_id, membership.user_id, account_id)


@endpoint(
    "PATCH",
    "/accounts/{account_id}",
    group="accounts",
    page="C6 Account Detail",
    owner="R",
    phase=2,
    access=Action.APPROVE_ANY,
)
async def patch_account(account_id: UUID, body: AccountPatchIn) -> AccountDetail:
    """Change account status or add domains (manager+)."""
    raise NotImplementedError


@real("patch_account")
async def patch_account_real(
    account_id: UUID,
    body: AccountPatchIn,
    membership: CurrentMembership,
) -> AccountDetail:
    async with org_session(membership.org_id) as session:
        return await patch_account_service(session, membership.org_id, account_id, body)
