"""Decision log audit service.

APIs:
- GET /log: filtered list with keyset cursor pagination.
- GET /log/{id}: why-replay assembly bundle (entry, related entries, evidence snapshot,
  rule metrics, proposed vs edited payload diff, execution attempts).
- GET /log/verify: hash chain verification across log ranges.
- POST /log/export & GET /log/export/{id}: export jobs.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.actions import ActionCard, Execution
from app.models.audit import DecisionLog
from app.models.brain import Finding, FindingEvidence
from app.models.tenancy import User
from app.schemas.cards import (
    ExecutionOut,
    LogDetailOut,
    LogEntryOut,
    LogExportIn,
    LogExportOut,
    LogVerifyOut,
    PayloadDiff,
)
from app.services.decision_log import verify_chain
from app.utils.errors import AppError
from app.utils.pagination import OrderKey, Page, PageParams, paginate


def _to_entry_out(row: DecisionLog, user_names: dict[str, str] | None = None) -> LogEntryOut:
    actor_name = None
    if user_names and row.actor_id and row.actor_type == "user":
        actor_name = user_names.get(row.actor_id)

    summary = None
    if isinstance(row.data, dict):
        summary = row.data.get("summary")
    if not summary:
        summary = f"{row.event} ({row.entity_type})"

    return LogEntryOut(
        id=row.id,
        ts=row.ts,
        actor_type=row.actor_type,
        actor_id=row.actor_id,
        actor_name=actor_name,
        event=row.event,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        account_id=row.account_id,
        summary=summary,
    )


async def list_decision_log(
    s: AsyncSession,
    *,
    org_id: UUID,
    page_params: PageParams,
    account_id: str | None = None,
    event: str | None = None,
    actor: str | None = None,
    from_: datetime | None = None,
    to_: datetime | None = None,
) -> Page[LogEntryOut]:
    """List decision log entries with filters and keyset pagination."""
    query = select(DecisionLog).where(DecisionLog.org_id == org_id)

    if account_id:
        try:
            acc_uid = UUID(account_id)
            query = query.where(DecisionLog.account_id == acc_uid)
        except ValueError as e:
            raise AppError("bad_request", f"Invalid account UUID: {account_id}") from e

    if event:
        query = query.where(DecisionLog.event == event)

    if actor:
        query = query.where(DecisionLog.actor_id == actor)

    if from_:
        query = query.where(DecisionLog.ts >= from_)

    if to_:
        query = query.where(DecisionLog.ts <= to_)

    order = [OrderKey(DecisionLog.ts, desc=True), OrderKey(DecisionLog.id, desc=True)]
    rows, next_cursor = await paginate(s, query, order, page_params)

    if not rows:
        return Page(items=[], next_cursor=None)

    # Fetch user names for actor_ids
    user_ids: set[UUID] = set()
    for item in rows:
        if item.actor_type == "user" and item.actor_id:
            try:
                user_ids.add(UUID(item.actor_id))
            except ValueError:
                pass

    user_names: dict[str, str] = {}
    if user_ids:
        u_stmt = select(User.id, User.name).where(User.id.in_(user_ids))
        u_res = await s.execute(u_stmt)
        for r in u_res.all():
            if r[1]:
                user_names[str(r[0])] = r[1]

    items = [_to_entry_out(r, user_names) for r in rows]
    return Page(items=items, next_cursor=next_cursor)


async def get_log_detail(s: AsyncSession, *, org_id: UUID, entry_id: int) -> LogDetailOut:
    """Reconstruct 'why replay' bundle for a decision log entry."""
    stmt = select(DecisionLog).where(DecisionLog.org_id == org_id, DecisionLog.id == entry_id)
    entry = (await s.execute(stmt)).scalar_one_or_none()
    if not entry:
        raise AppError("not_found", f"Decision log entry {entry_id} not found.")

    # 1. Fetch user name for entry
    user_names: dict[str, str] = {}
    if entry.actor_type == "user" and entry.actor_id:
        try:
            u_uid = UUID(entry.actor_id)
            u_name = (
                await s.execute(select(User.name).where(User.id == u_uid))
            ).scalar_one_or_none()
            if u_name:
                user_names[entry.actor_id] = u_name
        except ValueError:
            pass

    entry_out = _to_entry_out(entry, user_names)

    # 2. Fetch related entries
    related_query = (
        select(DecisionLog)
        .where(DecisionLog.org_id == org_id, DecisionLog.id != entry_id)
        .order_by(DecisionLog.ts.asc(), DecisionLog.id.asc())
        .limit(20)
    )
    if entry.entity_id and entry.account_id:
        related_query = related_query.where(
            (DecisionLog.entity_id == entry.entity_id)
            | (DecisionLog.account_id == entry.account_id)
        )
    elif entry.entity_id:
        related_query = related_query.where(DecisionLog.entity_id == entry.entity_id)
    elif entry.account_id:
        related_query = related_query.where(DecisionLog.account_id == entry.account_id)

    related_rows = (await s.execute(related_query)).scalars().all()
    related_out = [_to_entry_out(r) for r in related_rows]

    # 3. Evidence snapshot & Rule metrics
    evidence_snapshot: list[dict[str, Any]] = []
    rule_metrics: list[dict[str, Any]] = []
    if isinstance(entry.data, dict) and entry.data.get("evidence"):
        evidence_snapshot = list(entry.data["evidence"])
    if isinstance(entry.data, dict) and entry.data.get("rule_metrics"):
        rule_metrics = list(entry.data["rule_metrics"])

    # If evidence not in entry data, resolve from finding
    finding_id: UUID | None = None
    if entry.entity_type == "action_card" and entry.entity_id:
        card_stmt = select(ActionCard.finding_id).where(
            ActionCard.org_id == org_id, ActionCard.id == entry.entity_id
        )
        finding_id = (await s.execute(card_stmt)).scalar_one_or_none()
    elif entry.entity_type == "finding" and entry.entity_id:
        finding_id = entry.entity_id

    if finding_id and not evidence_snapshot:
        ev_stmt = select(FindingEvidence).where(
            FindingEvidence.org_id == org_id, FindingEvidence.finding_id == finding_id
        )
        ev_rows = (await s.execute(ev_stmt)).scalars().all()
        evidence_snapshot = [
            {
                "key": e.evidence_key,
                "kind": e.kind,
                "label": e.label,
                "detail": e.detail,
                "source": e.source,
            }
            for e in ev_rows
        ]

    if finding_id and not rule_metrics:
        f_stmt = select(Finding).where(Finding.org_id == org_id, Finding.id == finding_id)
        f_row = (await s.execute(f_stmt)).scalar_one_or_none()
        if f_row and f_row.categories:
            rule_metrics = [{"categories": f_row.categories, "severity": f_row.severity}]

    # 4. Proposed vs edited payload diff
    payload_diff: list[PayloadDiff] = []
    if entry.entity_type == "action_card" and entry.entity_id:
        c_stmt = select(ActionCard).where(
            ActionCard.org_id == org_id, ActionCard.id == entry.entity_id
        )
        card_row = (await s.execute(c_stmt)).scalar_one_or_none()
        if card_row and card_row.edited_payload:
            orig = card_row.payload or {}
            edited = card_row.edited_payload or {}
            all_keys = sorted(set(orig.keys()) | set(edited.keys()))
            for k in all_keys:
                if orig.get(k) != edited.get(k):
                    payload_diff.append(
                        PayloadDiff(
                            field=k,
                            proposed=str(orig.get(k)) if k in orig else None,
                            edited=str(edited.get(k)) if k in edited else None,
                        )
                    )

    # 5. Execution attempts
    executions: list[ExecutionOut] = []
    if entry.entity_type == "action_card" and entry.entity_id:
        ex_stmt = (
            select(Execution)
            .where(Execution.org_id == org_id, Execution.action_card_id == entry.entity_id)
            .order_by(Execution.attempt.asc())
        )
        ex_rows = (await s.execute(ex_stmt)).scalars().all()
        executions = [
            ExecutionOut(
                attempt=ex.attempt,
                status=ex.status,
                started_at=ex.started_at,
                finished_at=ex.finished_at,
                error=ex.error,
            )
            for ex in ex_rows
        ]

    return LogDetailOut(
        entry=entry_out,
        data=entry.data or {},
        related=related_out,
        evidence_snapshot=evidence_snapshot,
        rule_metrics=rule_metrics,
        payload_diff=payload_diff,
        executions=executions,
    )


async def verify_decision_log(
    s: AsyncSession,
    *,
    org_id: UUID,
    from_id: int | None = None,
    to_id: int | None = None,
) -> LogVerifyOut:
    """Verify hash chain integrity across range of decision log entries."""
    res = await verify_chain(s, org_id, from_id=from_id, to_id=to_id)
    return LogVerifyOut(ok=res.ok, checked=res.checked, first_bad_id=res.first_bad_id)


async def export_decision_log(
    s: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    export_in: LogExportIn,
) -> LogExportOut:
    """Start an export job for decision log records (CSV or JSON)."""
    import csv
    import io
    import json

    from app.utils.redis import get_redis

    job_id = uuid4()
    stmt = select(DecisionLog).where(DecisionLog.org_id == org_id)
    if export_in.from_:
        stmt = stmt.where(DecisionLog.ts >= export_in.from_)
    if export_in.to:
        stmt = stmt.where(DecisionLog.ts <= export_in.to)
    stmt = stmt.order_by(DecisionLog.id.asc())

    rows = (await s.execute(stmt)).scalars().all()
    fmt = (export_in.format or "csv").lower()

    if fmt == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(
            ["id", "ts", "actor_type", "actor_id", "event", "entity_type", "entity_id", "prev_hash", "hash"]
        )
        for r in rows:
            writer.writerow(
                [
                    r.id,
                    r.ts.isoformat(),
                    r.actor_type,
                    r.actor_id or "",
                    r.event,
                    r.entity_type,
                    str(r.entity_id or ""),
                    r.prev_hash,
                    r.hash,
                ]
            )
        payload = out.getvalue()
    else:
        records = [
            {
                "id": r.id,
                "ts": r.ts.isoformat(),
                "actor_type": r.actor_type,
                "actor_id": r.actor_id,
                "event": r.event,
                "entity_type": r.entity_type,
                "entity_id": str(r.entity_id) if r.entity_id else None,
                "prev_hash": r.prev_hash,
                "hash": r.hash,
                "data": r.data,
            }
            for r in rows
        ]
        payload = json.dumps(records, indent=2)

    try:
        r_client = await get_redis()
        await r_client.setex(f"log_export:{org_id}:{job_id}", 3600, payload)
    except Exception:
        pass

    return LogExportOut(
        job_id=job_id,
        status="done",
        download_url=f"/api/v1/log/export/{job_id}?format={fmt}",
    )


async def get_export_status(s: AsyncSession, *, org_id: UUID, job_id: str) -> LogExportOut:
    """Get status of an export job."""
    try:
        jid = UUID(job_id)
    except ValueError as e:
        raise AppError("bad_request", f"Invalid job UUID: {job_id}") from e

    return LogExportOut(
        job_id=jid,
        status="done",
        download_url=f"/api/v1/log/export/{job_id}",
    )
