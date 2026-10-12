"""Hand-off to the AI service (apps/ai) when AI_MODE=external.

  - ai_enhance_task: after a run committed a finding, ask the AI service to explain it and draft
    its pending cards. Retries with backoff while the service is unreachable; when it stays down the
    template explanation and cards of the run remain in place.
  - ai_extract_dispatch: beat task that lets the AI service read new emails/notes for signals.
  - ai_index_dispatch: beat task that lets the AI service embed new or changed records for
    Riddhi's retrieval index.

Only ids travel to the AI service. It reads and writes customer data through /internal/v1.
"""

import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import admin_session
from app.models.tenancy import Organization
from app.models.timeline import Account, Event
from app.schemas.accounts import MlScores
from app.services import ai_client
from app.services.internal_ai import TEXT_EVENT_TYPES
from app.utils.events import publish
from app.utils.time import utcnow
from app.workers.celery_app import celery_app, tenant_task

EXTRACT_BATCH = 50
INDEX_BATCH = 50


@tenant_task("run.ai_enhance", queue="run")
async def ai_enhance_task(
    _session: AsyncSession,
    org_id: UUID,
    account_id: str,
    finding_id: str,
    run_id: str,
    trigger: str = "manual",
) -> dict[str, Any]:
    if not ai_client.enabled():
        return {"status": "disabled"}
    accepted = await ai_client.request_run(
        org_id=org_id,
        account_id=UUID(str(account_id)),
        finding_id=UUID(str(finding_id)),
        run_id=UUID(str(run_id)),
        trigger=trigger,
    )
    return {"status": "requested" if accepted else "rejected"}


def _score(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "probability": raw["probability"],
        "band": raw["band"],
        "reasons": [
            {"text": r["text"], "direction": r["direction"]} for r in raw.get("reasons", [])[:5]
        ],
    }


@tenant_task("run.ai_scores", queue="run")
async def ai_scores_task(session: AsyncSession, org_id: UUID, account_id: str) -> dict[str, Any]:
    """Store the ML churn/expansion scores of an account (shown on Today and the account pages)."""
    if not ai_client.enabled():
        return {"status": "disabled"}
    aid = UUID(str(account_id))
    raw = await ai_client.fetch_scores(org_id=org_id, account_id=aid)
    if raw is None:
        return {"status": "unavailable"}
    churn, expansion = raw["churn"], raw["expansion"]
    trained_on = str(churn.get("trained_on") or "")
    scores = MlScores.model_validate(
        {
            "churn": _score(churn),
            "expansion": _score(expansion),
            "view": raw.get("view") or "stable",
            "model_version": churn.get("model"),
            "trained_on": trained_on or None,
            "synthetic": "SYNTHETIC" in trained_on.upper(),
            "scored_at": utcnow(),
        }
    )
    account = (
        await session.execute(select(Account).where(Account.id == aid, Account.org_id == org_id))
    ).scalar_one_or_none()
    if account is None:
        return {"status": "not_found"}
    account.ml_scores = scores.model_dump(mode="json")
    await session.flush()
    await publish(org_id, "account.updated", {"id": str(aid)})
    return {"status": "scored", "churn_band": scores.churn.band}


@celery_app.task(name="run.ai_extract_dispatch")
def ai_extract_dispatch() -> dict[str, int]:
    """Ask the AI service to extract signals for every active org that has unread text events."""

    async def _inner() -> dict[str, int]:
        if not ai_client.enabled():
            return {"dispatched": 0}
        async with admin_session() as s:
            stmt = (
                select(Event.org_id)
                .join(Organization, Organization.id == Event.org_id)
                .where(
                    Organization.status == "active",
                    Event.signals_extracted_at.is_(None),
                    Event.account_id.is_not(None),
                    Event.type.in_(TEXT_EVENT_TYPES),
                    func.length(func.coalesce(Event.body_text, "")) > 0,
                )
                .distinct()
            )
            org_ids = list((await s.execute(stmt)).scalars().all())
        dispatched = 0
        for oid in org_ids:
            out = await ai_client.request_extraction(org_id=oid, limit=EXTRACT_BATCH, wait=False)
            dispatched += 1 if out is not None else 0
        return {"dispatched": dispatched}

    return asyncio.run(_inner())


@celery_app.task(name="run.ai_index_dispatch")
def ai_index_dispatch() -> dict[str, int]:
    """Ask the AI service to embed new or changed records of every active org, so Riddhi can
    search them. The service asks the backend what is pending: an org with nothing new is a no-op."""

    async def _inner() -> dict[str, int]:
        if not ai_client.enabled():
            return {"dispatched": 0}
        async with admin_session() as s:
            org_ids = list(
                (await s.execute(select(Organization.id).where(Organization.status == "active")))
                .scalars()
                .all()
            )
        dispatched = 0
        for oid in org_ids:
            out = await ai_client.request_indexing(org_id=oid, limit=INDEX_BATCH, wait=False)
            dispatched += 1 if out is not None else 0
        return {"dispatched": dispatched}

    return asyncio.run(_inner())
