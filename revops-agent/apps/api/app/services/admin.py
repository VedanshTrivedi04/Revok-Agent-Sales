"""Platform superadmin service layer.

Rules:
1. ONLY uses the `admin` DB role with BYPASSRLS via `admin_session()`.
2. NEVER returns customer content or PII in responses: only counts,
   statuses, metadata, and connector error text.
3. Org suspension invalidates cached memberships in Redis so the 403
   org_suspended guard takes effect immediately.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import admin_session
from app.models.audit import FailedJob, FeatureFlag
from app.models.brain import Finding
from app.models.integrations import Integration
from app.models.tenancy import Membership, Organization
from app.models.timeline import Account
from app.schemas.identity import Ack
from app.schemas.ops import (
    AdminJobOut,
    AdminOrgDetail,
    AdminOrgOut,
    DataHealthOut,
    EvalRunIn,
    EvalSummary,
    FlagOut,
    FlagPutIn,
    LlmHealthOut,
)
from app.services.identity import DEFAULT_FEATURE_FLAGS
from app.utils.errors import AppError
from app.utils.pagination import OrderKey, Page, PageParams, paginate
from app.utils.redis import get_redis
from app.utils.time import utcnow

log = structlog.get_logger()


async def _invalidate_org_cache(org_id: UUID) -> None:
    """Invalidate all cached user memberships for this organization."""
    try:
        redis = get_redis()
        keys: list[str] = []
        async for key in redis.scan_iter(f"membership:{org_id}:*"):
            keys.append(key)
        if keys:
            await redis.delete(*keys)
    except Exception as e:
        log.warning("invalidate_org_cache_failed", org_id=str(org_id), error=str(e))


async def _build_admin_org_out(s: AsyncSession, org: Organization) -> AdminOrgOut:
    """Compute aggregate counts and health status for an organization."""
    members_count = (
        await s.scalar(
            select(func.count()).where(Membership.org_id == org.id, Membership.status == "active")
        )
        or 0
    )

    accounts_count = await s.scalar(select(func.count()).where(Account.org_id == org.id)) or 0

    last_sync = await s.scalar(
        select(func.max(Integration.last_sync_at)).where(Integration.org_id == org.id)
    )

    open_findings = (
        await s.scalar(
            select(func.count()).where(Finding.org_id == org.id, Finding.status == "open")
        )
        or 0
    )

    since_24h = utcnow() - timedelta(hours=24)
    failed_jobs_stmt = select(func.count()).where(
        FailedJob.failed_at >= since_24h,
        cast(FailedJob.args, String).like(f"%{org.id}%"),
    )
    failed_jobs_24h = (await s.scalar(failed_jobs_stmt)) or 0

    return AdminOrgOut(
        id=org.id,
        name=org.name,
        status=org.status,
        plan=org.plan,
        members=members_count,
        accounts=accounts_count,
        last_sync_at=last_sync,
        open_findings=open_findings,
        failed_jobs_24h=failed_jobs_24h,
        created_at=org.created_at,
    )


async def list_admin_orgs(page: PageParams) -> Page[AdminOrgOut]:
    """List all organizations with health counts and statuses (no customer content)."""
    async with admin_session() as s:
        order = [
            OrderKey(Organization.created_at, desc=True),
            OrderKey(Organization.id, desc=True),
        ]
        orgs, next_cursor = await paginate(
            s,
            select(Organization).where(Organization.status != "deleted"),
            order,
            page,
        )
        items = [await _build_admin_org_out(s, o) for o in orgs]
        return Page(items=items, next_cursor=next_cursor)


async def get_admin_org(org_id: UUID) -> AdminOrgDetail:
    """Get single organization health details. No customer PII or content included."""
    async with admin_session() as s:
        org = await s.get(Organization, org_id)
        if org is None or org.status == "deleted":
            raise AppError("not_found", f"Organization {org_id} not found")

        base = await _build_admin_org_out(s, org)

        integs = (
            (await s.execute(select(Integration).where(Integration.org_id == org_id)))
            .scalars()
            .all()
        )

        integrations_out: list[dict[str, Any]] = [
            {
                "provider": integ.provider,
                "status": integ.status,
                "last_sync_at": integ.last_sync_at.isoformat() if integ.last_sync_at else None,
            }
            for integ in integs
        ]

        # Recent system/connector error messages only (no customer content)
        recent_errors: list[str] = []
        for integ in integs:
            if integ.last_error:
                recent_errors.append(integ.last_error[:500])

        failed_jobs_stmt = (
            select(FailedJob.error)
            .where(
                cast(FailedJob.args, String).like(f"%{org_id}%"),
                FailedJob.error.isnot(None),
            )
            .order_by(FailedJob.failed_at.desc())
            .limit(10)
        )
        job_errors = (await s.execute(failed_jobs_stmt)).scalars().all()
        for err in job_errors:
            if err and err not in recent_errors:
                recent_errors.append(err[:500])

        return AdminOrgDetail(
            **base.model_dump(),
            integrations=integrations_out,
            recent_errors=recent_errors,
        )


async def suspend_org(org_id: UUID) -> AdminOrgOut:
    """Suspend an organization: all non-admin routes return 403 org_suspended."""
    async with admin_session() as s:
        org = await s.get(Organization, org_id)
        if org is None or org.status == "deleted":
            raise AppError("not_found", f"Organization {org_id} not found")

        org.status = "suspended"
        await s.flush()
        await _invalidate_org_cache(org_id)
        return await _build_admin_org_out(s, org)


async def unsuspend_org(org_id: UUID) -> AdminOrgOut:
    """Lift an organization suspension."""
    async with admin_session() as s:
        org = await s.get(Organization, org_id)
        if org is None or org.status == "deleted":
            raise AppError("not_found", f"Organization {org_id} not found")

        org.status = "active"
        await s.flush()
        await _invalidate_org_cache(org_id)
        return await _build_admin_org_out(s, org)


async def list_admin_jobs(page: PageParams) -> Page[AdminJobOut]:
    """List dead-lettered background jobs (args excluded to prevent leaking customer content)."""
    async with admin_session() as s:
        order = [
            OrderKey(FailedJob.failed_at, desc=True),
            OrderKey(FailedJob.id, desc=True),
        ]
        jobs, next_cursor = await paginate(s, select(FailedJob), order, page)

        items: list[AdminJobOut] = []
        for j in jobs:
            extracted_org: UUID | None = None
            if j.args and isinstance(j.args, list) and len(j.args) > 0:
                try:
                    extracted_org = UUID(str(j.args[0]))
                except (ValueError, TypeError):
                    pass

            items.append(
                AdminJobOut(
                    id=j.id,
                    task_name=j.task_name,
                    org_id=extracted_org,
                    error=j.error,
                    failed_at=j.failed_at,
                    retried_at=j.retried_at,
                )
            )

        return Page(items=items, next_cursor=next_cursor)


async def retry_admin_job(job_id: UUID) -> Ack:
    """Re-enqueue a dead-lettered task in Celery."""
    async with admin_session() as s:
        job = await s.get(FailedJob, job_id)
        if job is None:
            raise AppError("not_found", f"Failed job {job_id} not found")

        job.retried_at = utcnow()

        from app.workers.celery_app import celery_app

        args = job.args if isinstance(job.args, list) else []
        celery_app.send_task(job.task_name, args=args)

        return Ack(ok=True)


async def discard_admin_job(job_id: UUID) -> Ack:
    """Discard a dead-lettered task."""
    async with admin_session() as s:
        job = await s.get(FailedJob, job_id)
        if job is None:
            raise AppError("not_found", f"Failed job {job_id} not found")

        await s.delete(job)
        return Ack(ok=True)


async def llm_health() -> LlmHealthOut:
    """Placeholder health check for AI services in template mode."""
    return LlmHealthOut(
        status="ok",
        mode="template",
        latency_ms=5,
        model=None,
    )


async def list_evals() -> list[EvalSummary]:
    """Placeholder eval summary list."""
    return []


async def run_evals(body: EvalRunIn) -> Ack:
    """Placeholder eval trigger."""
    return Ack(ok=True)


async def list_flags() -> list[FlagOut]:
    """List all feature flags with default and per-org overrides."""
    async with admin_session() as s:
        rows = (await s.execute(select(FeatureFlag))).scalars().all()
        flag_dict: dict[str, FlagOut] = {}

        # Prepopulate standard defaults
        for k, v in DEFAULT_FEATURE_FLAGS.items():
            flag_dict[k] = FlagOut(key=k, default=v, per_org={})

        for r in rows:
            flag_dict[r.key] = FlagOut(
                key=r.key,
                default=r.default,
                per_org=r.per_org or {},
            )

        return list(flag_dict.values())


async def put_flag(body: FlagPutIn) -> FlagOut:
    """Create or update a feature flag with default and per-org overrides."""
    async with admin_session() as s:
        flag = await s.get(FeatureFlag, body.key)
        if flag is None:
            default_val = (
                body.default
                if body.default is not None
                else DEFAULT_FEATURE_FLAGS.get(body.key, False)
            )
            flag = FeatureFlag(
                key=body.key,
                default=default_val,
                per_org=body.per_org or {},
            )
            s.add(flag)
        else:
            if body.default is not None:
                flag.default = body.default
            if body.per_org is not None:
                flag.per_org = body.per_org

        await s.flush()
        return FlagOut(key=flag.key, default=flag.default, per_org=flag.per_org or {})


async def get_data_health() -> DataHealthOut:
    """Compute data health metrics across all organizations using admin session."""
    from app.models.timeline import Contact, Event

    async with admin_session() as s:
        # Accounts missing renewal date
        stmt_missing_renewal = select(func.count(Account.id)).where(Account.renewal_date.is_(None))
        missing_renewal = (await s.execute(stmt_missing_renewal)).scalar() or 0

        # Unmapped owners
        stmt_unmapped_owners = select(func.count(Account.id)).where(Account.owner_user_id.is_(None))
        unmapped_owners = (await s.execute(stmt_unmapped_owners)).scalar() or 0

        # Orphan events
        stmt_orphan_events = select(func.count(Event.id)).where(Event.account_id.is_(None))
        orphan_events = (await s.execute(stmt_orphan_events)).scalar() or 0

        # Contacts without account
        stmt_contacts_no_acc = select(func.count(Contact.id)).where(Contact.account_id.is_(None))
        contacts_without_account = (await s.execute(stmt_contacts_no_acc)).scalar() or 0

        return DataHealthOut(
            accounts_missing_renewal_date=missing_renewal,
            unmapped_owners=unmapped_owners,
            orphan_events=orphan_events,
            contacts_without_account=contacts_without_account,
            details={
                "missing_renewal_count": missing_renewal,
                "unmapped_owners_count": unmapped_owners,
                "orphan_events_count": orphan_events,
                "contacts_without_account_count": contacts_without_account,
            },
        )
