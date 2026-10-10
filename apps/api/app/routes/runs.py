from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query

from app.contract import endpoint
from app.permissions import Action
from app.schemas.ops import RunDetail, RunOut, RunStatus
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


@endpoint(
    "GET", "/runs/{run_id}", group="runs", page=PAGE, owner="R", phase=3, access=Action.VIEW_RUNS
)
async def get_run(run_id: UUID) -> RunDetail:
    """Run steps, timings and trace link."""
    raise NotImplementedError
