"""Append-only, hash-chained decision log (one chain per org).

hash = sha256(prev_hash || canonical_json(row without hash)); the first row's prev_hash is
"GENESIS". `log()` must be called in the SAME transaction as the state change it records
(agent.md hard rule 8). The advisory lock serializes writers per org so the chain never forks.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import DecisionLog
from app.utils.canonical import canonical_json
from app.utils.time import utcnow

GENESIS = "GENESIS"


def compute_hash(prev_hash: str, row: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + canonical_json(row)).encode("utf-8")).hexdigest()


def _hashable(
    *, org_id: UUID, ts: datetime, actor_type: str, actor_id: str | None, event: str,
    entity_type: str, entity_id: UUID | None, account_id: UUID | None,
    data: dict[str, Any], prev_hash: str,
) -> dict[str, Any]:  # fmt: skip
    return {
        "org_id": org_id, "ts": ts, "actor_type": actor_type, "actor_id": actor_id,
        "event": event, "entity_type": entity_type, "entity_id": entity_id,
        "account_id": account_id, "data": data, "prev_hash": prev_hash,
    }  # fmt: skip


async def log(
    s: AsyncSession,
    *,
    org_id: UUID,
    actor_type: str,
    actor_id: str | UUID | None,
    event: str,
    entity_type: str,
    entity_id: UUID | None,
    account_id: UUID | None = None,
    data: dict[str, Any] | None = None,
) -> DecisionLog:
    """Append one entry. Runs inside the caller's transaction (RLS session for `org_id`)."""
    await s.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"dlog:{org_id}"})
    prev = await s.scalar(
        select(DecisionLog.hash)
        .where(DecisionLog.org_id == org_id)
        .order_by(DecisionLog.id.desc())
        .limit(1)
    )
    fields = _hashable(
        org_id=org_id, ts=utcnow(), actor_type=actor_type,
        actor_id=str(actor_id) if actor_id is not None else None, event=event,
        entity_type=entity_type, entity_id=entity_id, account_id=account_id,
        data=data or {}, prev_hash=prev or GENESIS,
    )  # fmt: skip
    entry = DecisionLog(**fields, hash=compute_hash(fields["prev_hash"], fields))
    s.add(entry)
    await s.flush()
    return entry


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    checked: int
    first_bad_id: int | None = None


async def verify_chain(
    s: AsyncSession, org_id: UUID, from_id: int | None = None, to_id: int | None = None
) -> VerifyResult:
    """Recompute every hash in [from_id, to_id] and check each prev_hash links to its predecessor.

    Detects edited rows (hash mismatch), deleted rows and forged inserts (broken link at the
    row after the gap). Returns the id of the first offending row.
    """
    q = select(DecisionLog).where(DecisionLog.org_id == org_id).order_by(DecisionLog.id)
    if from_id is not None:
        q = q.where(DecisionLog.id >= from_id)
    if to_id is not None:
        q = q.where(DecisionLog.id <= to_id)
    rows = (await s.execute(q)).scalars().all()
    if not rows:
        return VerifyResult(True, 0)

    expected_prev = GENESIS
    if from_id is not None:
        before = await s.scalar(
            select(DecisionLog.hash)
            .where(DecisionLog.org_id == org_id, DecisionLog.id < rows[0].id)
            .order_by(DecisionLog.id.desc())
            .limit(1)
        )
        expected_prev = before or GENESIS

    for r in rows:
        fields = _hashable(
            org_id=r.org_id, ts=r.ts, actor_type=r.actor_type, actor_id=r.actor_id,
            event=r.event, entity_type=r.entity_type, entity_id=r.entity_id,
            account_id=r.account_id, data=r.data, prev_hash=r.prev_hash,
        )  # fmt: skip
        if r.prev_hash != expected_prev or compute_hash(r.prev_hash, fields) != r.hash:
            return VerifyResult(False, len(rows), r.id)
        expected_prev = r.hash
    return VerifyResult(True, len(rows))
