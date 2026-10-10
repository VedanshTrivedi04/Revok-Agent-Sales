from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query

from app.contract import endpoint
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
from app.utils.pagination import Page, PageParams, page_params

Paging = Annotated[PageParams, Depends(page_params)]


@endpoint("GET", "/today", group="today", page="C1 Today", owner="R", phase=3)
async def get_today(
    type: Annotated[Literal["risk", "expansion", "all"], Query()] = "all",
    owner: Annotated[str, Query(description="me | all | <user_id>")] = "me",
) -> TodayResponse:
    """Ranked open findings with account summary and pending card counts."""
    raise NotImplementedError


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


@endpoint(
    "GET", "/accounts/{account_id}", group="accounts", page="C6 Account Detail", owner="R", phase=2
)
async def get_account(account_id: UUID) -> AccountDetail:
    """Account detail with metrics and open findings."""
    raise NotImplementedError


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
