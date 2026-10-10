"""Entity match review queue service (R2-03).

Provides:
  - list_entity_reviews_service: lists ambiguous events waiting for manual resolution.
  - resolve_entity_review_service: resolves review by assigning to account (optionally applying domain rule) or ignoring.
"""

from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.timeline import Account, EntityMatchReview, Event
from app.schemas.identity import Ack
from app.schemas.ops import EntityReviewOut, EntityReviewResolveIn
from app.services.decision_log import log as decision_log
from app.services.freemail import is_freemail_domain
from app.utils.errors import AppError
from app.utils.pagination import OrderKey, Page, PageParams, paginate
from app.utils.time import utcnow


async def list_entity_reviews_service(
    session: AsyncSession,
    org_id: UUID,
    page: PageParams,
    *,
    status: str = "open",
) -> Page[EntityReviewOut]:
    """List entity match reviews for the organization."""
    stmt = select(EntityMatchReview).where(
        EntityMatchReview.org_id == org_id,
        EntityMatchReview.status == status,
    )
    order = [
        OrderKey(EntityMatchReview.created_at, desc=True),
        OrderKey(EntityMatchReview.id, desc=False),
    ]

    rows, next_cursor = await paginate(session, stmt, order, page)

    # Pre-load candidate account names and event titles
    all_candidate_ids: set[UUID] = set()
    event_ids: set[UUID] = set()
    for rev in rows:
        for cid in rev.candidate_account_ids:
            all_candidate_ids.add(cid)
        if rev.event_id:
            event_ids.add(rev.event_id)

    account_names: dict[UUID, str] = {}
    if all_candidate_ids:
        acc_stmt = select(Account.id, Account.name).where(
            Account.org_id == org_id,
            Account.id.in_(all_candidate_ids),
        )
        for aid, aname in (await session.execute(acc_stmt)).all():
            account_names[aid] = aname

    event_titles: dict[UUID, str] = {}
    if event_ids:
        evt_stmt = select(Event.id, Event.title, Event.summary).where(
            Event.org_id == org_id,
            Event.id.in_(event_ids),
        )
        for eid, etitle, esummary in (await session.execute(evt_stmt)).all():
            event_titles[eid] = etitle or esummary or "Untitled Event"

    out_items = [
        EntityReviewOut(
            id=rev.id,
            event_id=rev.event_id,
            event_title=event_titles.get(rev.event_id),
            candidate_account_ids=rev.candidate_account_ids,
            candidate_account_names=[
                account_names.get(cid, "Unknown Account") for cid in rev.candidate_account_ids
            ],
            reason=rev.reason,
            status=cast(Any, rev.status),
            created_at=rev.created_at,
        )
        for rev in rows
    ]

    return Page(
        items=out_items,
        next_cursor=next_cursor,
    )


async def resolve_entity_review_service(
    session: AsyncSession,
    org_id: UUID,
    user_id: UUID,
    review_id: UUID,
    body: EntityReviewResolveIn,
) -> Ack:
    """Resolve an entity review item."""
    stmt = select(EntityMatchReview).where(
        EntityMatchReview.id == review_id,
        EntityMatchReview.org_id == org_id,
    )
    review = (await session.execute(stmt)).scalar_one_or_none()
    if review is None:
        raise AppError("not_found", "Entity review item not found", status=404)

    evt_stmt = select(Event).where(Event.id == review.event_id, Event.org_id == org_id)
    event = (await session.execute(evt_stmt)).scalar_one_or_none()

    if body.ignore:
        review.status = "ignored"
        review.resolved_by = user_id
        if event:
            event.match_method = "none"
        await session.flush()
        return Ack(ok=True)

    if not body.account_id:
        raise AppError(
            "validation_error",
            "Either account_id must be provided or ignore must be true",
            status=422,
        )

    # Validate target account
    acc_stmt = select(Account).where(Account.id == body.account_id, Account.org_id == org_id)
    account = (await session.execute(acc_stmt)).scalar_one_or_none()
    if account is None:
        raise AppError("not_found", "Target account not found", status=404)

    review.status = "resolved"
    review.resolved_account_id = body.account_id
    review.resolved_by = user_id

    extracted_domain: str | None = None
    if event:
        event.account_id = body.account_id
        event.match_method = "manual"
        event.match_confidence = 1.0

        # Extract domain from participants
        for p in event.participants or []:
            email = p.get("email") if isinstance(p, dict) else str(p)
            if email and "@" in email:
                dom = email.split("@", 1)[1].strip().lower()
                if dom.startswith("www."):
                    dom = dom[4:]
                if not is_freemail_domain(dom):
                    extracted_domain = dom
                    break

    # If apply_to_domain is requested, persist domain on account and reassign related events
    apply_domain_flag = getattr(body, "apply_to_domain", False)
    if apply_domain_flag and extracted_domain:
        existing_domains = list(account.domains or [])
        if extracted_domain not in existing_domains:
            existing_domains.append(extracted_domain)
            account.domains = existing_domains

        # Also reassign other open reviews that share this domain
        open_reviews_stmt = (
            select(EntityMatchReview, Event)
            .join(Event, EntityMatchReview.event_id == Event.id)
            .where(
                EntityMatchReview.org_id == org_id,
                EntityMatchReview.status == "open",
                EntityMatchReview.id != review_id,
            )
        )
        open_pairs = (await session.execute(open_reviews_stmt)).all()
        for other_rev, other_evt in open_pairs:
            for p in other_evt.participants or []:
                em = p.get("email") if isinstance(p, dict) else str(p)
                if em and f"@{extracted_domain}" in em.lower():
                    other_rev.status = "resolved"
                    other_rev.resolved_account_id = body.account_id
                    other_rev.resolved_by = user_id
                    other_evt.account_id = body.account_id
                    other_evt.match_method = "manual"
                    other_evt.match_confidence = 1.0
                    break

    # Audit log
    await decision_log(
        session,
        org_id=org_id,
        actor_type="user",
        actor_id=str(user_id),
        event="review.resolved",
        entity_type="entity_review",
        entity_id=review_id,
        account_id=body.account_id,
        data={
            "account_id": str(body.account_id),
            "applied_to_domain": apply_domain_flag,
            "domain": extracted_domain,
            "resolved_at": utcnow().isoformat(),
        },
    )

    await session.flush()
    return Ack(ok=True)
