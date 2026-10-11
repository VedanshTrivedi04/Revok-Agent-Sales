from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query

from app.auth.deps import CurrentMembership
from app.contract import endpoint, real
from app.db.session import org_session
from app.permissions import Action
from app.schemas.accounts import RunTriggerOut
from app.schemas.ops import RunDetail, RunOut, RunStatus
from app.services.runs import get_run_service, list_runs_service, retry_run_service
from app.utils.pagination import Page, PageParams, page_params

PAGE = "C10 Agent Runs"
Paging = Annotated[PageParams, Depends(page_params)]


@endpoint("GET", "/runs", group="runs", page=PAGE, owner="R", phase=3, access=Action.VIEW_RUNS)
async def list_runs(
    page: Paging,
    account_id: Annotated[UUID | None, Query()] = None,
    status: Annotated[RunStatus | None, Query()] = None,
) -> Page[RunOut]:
    """Agent runs (manager+)."""
    raise NotImplementedError


@real("list_runs")
async def list_runs_real(
    membership: CurrentMembership,
    page: Paging,
    account_id: Annotated[UUID | None, Query()] = None,
    status: Annotated[RunStatus | None, Query()] = None,
) -> Page[RunOut]:
    async with org_session(membership.org_id) as session:
        return await list_runs_service(
            session,
            membership.org_id,
            page,
            account_id=account_id,
            status=status,
        )


@endpoint(
    "POST",
    "/runs/{run_id}/retry",
    group="runs",
    page=PAGE,
    owner="R",
    phase=6,
    access=Action.VIEW_RUNS,
    status_code=202,
)
async def retry_run(run_id: UUID) -> RunTriggerOut:
    """Start a new manual run for the account of a failed or skipped run (manager+)."""
    raise NotImplementedError


@real("retry_run")
async def retry_run_real(run_id: UUID, membership: CurrentMembership) -> RunTriggerOut:
    async with org_session(membership.org_id) as session:
        return await retry_run_service(session, membership.org_id, membership.user_id, run_id)


@endpoint(
    "GET", "/runs/{run_id}", group="runs", page=PAGE, owner="R", phase=3, access=Action.VIEW_RUNS
)
async def get_run(run_id: UUID) -> RunDetail:
    """Run steps, timings and trace link."""
    raise NotImplementedError


@real("get_run")
async def get_run_real(
    run_id: UUID,
    membership: CurrentMembership,
) -> RunDetail:
    async with org_session(membership.org_id) as session:
        return await get_run_service(session, membership.org_id, run_id)
