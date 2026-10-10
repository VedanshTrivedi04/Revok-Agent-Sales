"""Agent Runs services for listing and detail inspection (R3-08)."""

from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brain import AgentRun
from app.models.timeline import Account
from app.schemas.ops import RunDetail, RunOut, RunStep
from app.utils.errors import AppError
from app.utils.pagination import OrderKey, Page, PageParams, paginate


async def list_runs_service(
    session: AsyncSession,
    org_id: UUID,
    page: PageParams,
    *,
    account_id: UUID | None = None,
    status: str | None = None,
) -> Page[RunOut]:
    """List agent runs with keyset pagination and pre-fetched account names."""
    stmt = select(AgentRun).where(AgentRun.org_id == org_id)
    if account_id:
        stmt = stmt.where(AgentRun.account_id == account_id)
    if status:
        stmt = stmt.where(AgentRun.status == status)

    order = [
        OrderKey(AgentRun.created_at, desc=True),
        OrderKey(AgentRun.id, desc=False),
    ]
    rows, next_cursor = await paginate(session, stmt, order, page)

    # Pre-fetch account names
    acc_ids = {r.account_id for r in rows if r.account_id}
    acc_names: dict[UUID, str] = {}
    if acc_ids:
        acc_stmt = select(Account.id, Account.name).where(
            Account.org_id == org_id,
            Account.id.in_(acc_ids),
        )
        for aid, aname in (await session.execute(acc_stmt)).all():
            acc_names[aid] = aname

    items = [
        RunOut(
            id=r.id,
            account_id=r.account_id,
            account_name=acc_names.get(r.account_id) if r.account_id else None,
            trigger=cast(Any, r.trigger),
            status=cast(Any, r.status),
            started_at=r.started_at,
            finished_at=r.finished_at,
            stats=r.stats or {},
            model=r.model,
            error=r.error,
        )
        for r in rows
    ]

    return Page(items=items, next_cursor=next_cursor)


async def get_run_service(
    session: AsyncSession,
    org_id: UUID,
    run_id: UUID,
) -> RunDetail:
    """Get full details of an agent run including step breakdown and timings."""
    stmt = select(AgentRun).where(AgentRun.id == run_id, AgentRun.org_id == org_id)
    run = (await session.execute(stmt)).scalar_one_or_none()
    if not run:
        raise AppError("not_found", "Agent run not found", status=404)

    acc_name: str | None = None
    if run.account_id:
        acc_stmt = select(Account.name).where(
            Account.id == run.account_id, Account.org_id == org_id
        )
        acc_name = (await session.execute(acc_stmt)).scalar()

    stats = run.stats or {}
    raw_steps = stats.get("steps") or []
    steps = [
        RunStep(
            name=s.get("name", "step"),
            status=cast(Any, s.get("status", "ok")),
            duration_ms=s.get("duration_ms"),
            detail=s.get("detail"),
        )
        for s in raw_steps
        if isinstance(s, dict)
    ]

    return RunDetail(
        id=run.id,
        account_id=run.account_id,
        account_name=acc_name,
        trigger=cast(Any, run.trigger),
        status=cast(Any, run.status),
        started_at=run.started_at,
        finished_at=run.finished_at,
        stats=stats,
        model=run.model,
        error=run.error,
        steps=steps,
        prompt_versions=run.prompt_versions or {},
        trace_url=None,
    )
