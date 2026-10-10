"""Usage data ingestion service: batch API ingest, per-row validation, and CSV job handling."""

import csv
import io
import json
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.timeline import Account, UsageSnapshot
from app.schemas.integrations import (
    CsvJobOut,
    CsvMappingIn,
    UsageIngestOut,
    UsageRejected,
    UsageRowIn,
)
from app.utils.errors import AppError
from app.utils.redis import get_redis
from app.utils.time import utcnow


async def resolve_accounts_map(
    session: AsyncSession, org_id: UUID, keys_with_types: Sequence[tuple[str, str]]
) -> dict[tuple[str, str], UUID]:
    """Preload account lookups for the batch to avoid N+1 queries."""
    stmt = select(Account).where(Account.org_id == org_id)
    accounts = (await session.execute(stmt)).scalars().all()

    resolved: dict[tuple[str, str], UUID] = {}
    for acc in accounts:
        # Map domains
        for d in acc.domains or []:
            resolved[(d.lower(), "domain")] = acc.id
        # Map external ids
        ext_ids = acc.external_ids or {}
        for k, v in ext_ids.items():
            resolved[(str(v), "external_id")] = acc.id
            if k in ("hubspot", "hubspot_id", "hs_object_id"):
                resolved[(str(v), "hubspot_id")] = acc.id

    mapping: dict[tuple[str, str], UUID] = {}
    for key, ktype in keys_with_types:
        lookup_key = (key.lower() if ktype == "domain" else key, ktype)
        if lookup_key in resolved:
            mapping[(key, ktype)] = resolved[lookup_key]

    return mapping


async def ingest_usage_service(
    session: AsyncSession,
    org_id: UUID,
    rows: list[UsageRowIn],
    *,
    source: str = "api",
    received_at: datetime | None = None,
) -> UsageIngestOut:
    if len(rows) > 1000:
        raise AppError("validation_error", "Maximum 1,000 rows per batch", status=422)

    now_dt = received_at or utcnow()
    rejected: list[UsageRejected] = []
    accepted_rows: list[tuple[int, UUID, UsageRowIn]] = []

    # Check for duplicates within batch: (account_key, period_start, granularity)
    seen_in_batch: set[tuple[str, date, str]] = set()

    # Pre-resolve accounts
    keys_with_types = [(r.account_key, r.account_key_type) for r in rows]
    accounts_map = await resolve_accounts_map(session, org_id, keys_with_types)

    for i, row in enumerate(rows):
        # 1. Duplicate in batch check
        batch_key = (row.account_key, row.period_start, row.granularity)
        if batch_key in seen_in_batch:
            rejected.append(UsageRejected(index=i, reason="duplicate_in_batch"))
            continue
        seen_in_batch.add(batch_key)

        # 2. Negative value check
        if (
            row.active_users < 0
            or (row.seats_used is not None and row.seats_used < 0)
            or (row.logins is not None and row.logins < 0)
        ):
            rejected.append(UsageRejected(index=i, reason="negative_value"))
            continue

        # 3. Invalid date / period check
        if row.period_end is not None and row.period_end < row.period_start:
            rejected.append(UsageRejected(index=i, reason="invalid_date"))
            continue

        # 4. Granularity mismatch check
        if row.granularity == "week":
            expected_days = 7
            if row.period_end is not None:
                delta_days = (row.period_end - row.period_start).days
                if delta_days != expected_days and delta_days != 6:
                    rejected.append(UsageRejected(index=i, reason="granularity_mismatch"))
                    continue
        elif row.granularity == "day":
            if row.period_end is not None:
                delta_days = (row.period_end - row.period_start).days
                if delta_days not in (0, 1):
                    rejected.append(UsageRejected(index=i, reason="granularity_mismatch"))
                    continue

        # 5. Unknown account check
        account_id = accounts_map.get((row.account_key, row.account_key_type))
        if account_id is None:
            rejected.append(UsageRejected(index=i, reason="unknown_account"))
            continue

        accepted_rows.append((i, account_id, row))

    # Perform upserts
    for _, account_id, row in accepted_rows:
        end_date = row.period_end or (
            row.period_start + timedelta(days=6 if row.granularity == "week" else 0)
        )

        stmt = (
            select(UsageSnapshot)
            .where(
                UsageSnapshot.org_id == org_id,
                UsageSnapshot.account_id == account_id,
                UsageSnapshot.period_start == row.period_start,
                UsageSnapshot.granularity == row.granularity,
            )
            .with_for_update()
        )

        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is None:
            snapshot = UsageSnapshot(
                org_id=org_id,
                account_id=account_id,
                period_start=row.period_start,
                period_end=end_date,
                granularity=row.granularity,
                active_users=row.active_users,
                seats_used=row.seats_used,
                logins=row.logins,
                key_events=row.key_events or {},
                source=source,
            )
            session.add(snapshot)
        else:
            # Never overwrite with older received_at
            if existing.updated_at and existing.updated_at > now_dt:
                continue

            existing.period_end = end_date
            existing.active_users = row.active_users
            existing.seats_used = row.seats_used
            existing.logins = row.logins
            existing.key_events = row.key_events or {}
            existing.source = source
            existing.updated_at = now_dt

    await session.flush()
    return UsageIngestOut(
        accepted=len(accepted_rows),
        rejected=rejected,
    )


async def create_csv_job(
    session: AsyncSession,
    org_id: UUID,
    file_bytes: bytes,
    mapping_raw: str,
) -> CsvJobOut:
    try:
        mapping_dict = json.loads(mapping_raw)
        mapping = CsvMappingIn(**mapping_dict)
    except Exception as e:
        raise AppError("validation_error", f"Invalid mapping JSON: {e}", status=422) from e

    job_id = uuid4()
    redis = get_redis()
    job_key = f"csv_job:{org_id}:{job_id}"

    # Parse CSV content
    text_stream = io.StringIO(file_bytes.decode("utf-8-sig", errors="replace"))
    reader = csv.DictReader(text_stream)

    rows: list[UsageRowIn] = []
    parse_errors: list[UsageRejected] = []

    for idx, row_dict in enumerate(reader):
        try:
            account_key = row_dict.get(mapping.account_key, "").strip()
            period_str = row_dict.get(mapping.period_start, "").strip()
            p_start = date.fromisoformat(period_str)
            active_u = int(row_dict.get(mapping.active_users, 0))
            seats = (
                int(row_dict[mapping.seats_used])
                if mapping.seats_used and row_dict.get(mapping.seats_used)
                else None
            )
            logins = (
                int(row_dict[mapping.logins])
                if mapping.logins and row_dict.get(mapping.logins)
                else None
            )

            rows.append(
                UsageRowIn(
                    account_key=account_key,
                    account_key_type=mapping.account_key_type,
                    period_start=p_start,
                    granularity=mapping.granularity,
                    active_users=active_u,
                    seats_used=seats,
                    logins=logins,
                )
            )
        except Exception:
            parse_errors.append(UsageRejected(index=idx, reason="invalid_date"))

    result = await ingest_usage_service(session, org_id, rows, source="csv")
    all_errors = parse_errors + result.rejected

    job_data = {
        "job_id": str(job_id),
        "status": "done",
        "progress": 1.0,
        "accepted": result.accepted,
        "errors": [e.model_dump() for e in all_errors],
    }
    await redis.set(job_key, json.dumps(job_data), ex=86400)

    return CsvJobOut(
        job_id=job_id,
        status="done",
        progress=1.0,
        accepted=result.accepted,
        errors=all_errors,
    )


async def get_csv_job(org_id: UUID, job_id: UUID) -> CsvJobOut:
    redis = get_redis()
    job_key = f"csv_job:{org_id}:{job_id}"
    raw = await redis.get(job_key)
    if raw is None:
        raise AppError("not_found", "CSV job not found", status=404)
    data = json.loads(raw)
    return CsvJobOut(
        job_id=UUID(data["job_id"]),
        status=data["status"],
        progress=data["progress"],
        accepted=data["accepted"],
        errors=[UsageRejected(**e) for e in data.get("errors", [])],
    )
