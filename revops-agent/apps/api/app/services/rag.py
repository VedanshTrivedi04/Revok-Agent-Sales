"""Riddhi's retrieval index: which records are searchable, and the similarity search itself.

The backend owns the text and the vectors (table `rag_chunks`, tenant RLS); the AI service only
turns text into vectors. Three kinds of record are indexed, each rendered to plain text here:
findings (with their claims and evidence), action cards (with the drafted text) and timeline
events. A record is embedded again when its rendered text changes.

Search runs in pgvector (HNSW over `embedding::vector`) when the database has the extension,
and as an exact scan in Python when it does not, so a plain Postgres still works.
"""

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.actions import ActionCard
from app.models.brain import Finding, FindingEvidence
from app.models.rag import EMBEDDING_DIM, RagChunk
from app.models.timeline import Account, Event
from app.schemas.internal import (
    RagChunksIn,
    RagChunksSavedOut,
    RagDocument,
    RagPassage,
    RagPendingOut,
    RagSearchIn,
    RagSearchOut,
)
from app.utils.errors import AppError
from app.utils.ids import new_id

SCAN_PER_SOURCE = 1000  # most recent records of each kind that are kept searchable
SCAN_ROWS = 5000  # passages ranked in Python when the database has no pgvector
_LEGAL_SUFFIX = re.compile(
    r"[\s,]+(corp|corporation|inc|ltd|llc|limited|co|company|gmbh|pvt|plc)\.?$", re.I
)


@dataclass(frozen=True)
class Doc:
    source_type: str
    source_id: UUID
    account_id: UUID | None
    account_name: str | None
    title: str
    text: str
    occurred_at: datetime | None

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(f"{self.title}\n{self.text}".encode()).hexdigest()[:32]


# ------------------------------------------------------------------ records as text
def _texts(items: Any) -> list[str]:
    """Claims, unknowns and contradictions are stored as strings or as {"text": ...} objects."""
    out = []
    for item in items or []:
        value = item.get("text") if isinstance(item, dict) else item
        if isinstance(value, str) and value.strip():
            out.append(value.strip())
    return out


def _finding_doc(f: Finding, account: str | None, evidence: list[FindingEvidence]) -> Doc:
    lines = [
        f"{f.type.capitalize()} finding for {account or 'an account'}: {f.title}",
        f"Status: {f.status}. Severity: {f.severity}. "
        f"Priority score: {float(f.priority_score):.1f}.",
    ]
    if f.summary:
        lines.append(f"Summary: {f.summary}")
    for heading, items in (
        ("Why", _texts(f.claims)),
        (
            "Evidence",
            [e.label + (f" ({e.detail})" if e.detail else "") for e in evidence],
        ),
        ("Not confirmed", _texts(f.unknowns)),
        ("Signals that disagree", _texts(f.contradictions)),
    ):
        if items:
            lines += [f"{heading}:", *(f"- {item}" for item in items)]
    if f.dismissed_reason:
        note = f" {f.dismissed_note}" if f.dismissed_note else ""
        lines.append(f"Dismissed: {f.dismissed_reason.replace('_', ' ')}.{note}")
    return Doc(
        "finding", f.id, f.account_id, account, f"Finding: {f.title}", "\n".join(lines),
        f.last_seen_at,
    )  # fmt: skip


def _card_doc(c: ActionCard, account: str | None) -> Doc:
    payload = c.edited_payload or c.payload or {}
    lines = [
        f"Proposed action for {account or 'an account'}: {c.title}",
        f"Type: {c.type.replace('_', ' ')}. Status: {c.status.replace('_', ' ')}. Tier {c.tier}.",
    ]
    if c.rationale:
        lines.append(f"Reason: {c.rationale}")
    for key, label in (("subject", "Subject"), ("body_text", "Text"), ("body", "Text"), ("text", "Text")):  # fmt: skip
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            lines.append(f"{label}: {value.strip()}")
    for change in payload.get("changes") or []:
        if isinstance(change, dict):
            lines.append(
                f"Change {change.get('object')} {change.get('field')}: "
                f"{change.get('before')} -> {change.get('after')}"
            )
    if c.rejection_reason:
        note = f" {c.rejection_note}" if c.rejection_note else ""
        lines.append(f"Rejected: {c.rejection_reason.replace('_', ' ')}.{note}")
    return Doc(
        "card", c.id, c.account_id, account, f"Action: {c.title}", "\n".join(lines), c.created_at
    )


def _event_doc(e: Event, account: str | None) -> Doc:
    kind = e.type.replace("_", " ").capitalize()
    subject = e.title or "(no subject)"
    lines = [f"{kind} with {account or 'an account'} on {e.occurred_at.date().isoformat()}: {subject}"]  # fmt: skip
    lines += [part.strip() for part in (e.summary, e.body_text) if part and part.strip()]
    return Doc(
        "event", e.id, e.account_id, account, f"{kind}: {subject}", "\n".join(lines), e.occurred_at
    )


async def _evidence(s: AsyncSession, org_id: UUID, finding_ids: list[UUID]) -> dict[UUID, list[FindingEvidence]]:  # fmt: skip
    out: dict[UUID, list[FindingEvidence]] = {}
    if not finding_ids:
        return out
    rows = await s.execute(
        select(FindingEvidence)
        .where(FindingEvidence.org_id == org_id, FindingEvidence.finding_id.in_(finding_ids))
        .order_by(FindingEvidence.finding_id, FindingEvidence.evidence_key)
    )
    for ev in rows.scalars():
        out.setdefault(ev.finding_id, []).append(ev)
    return out


async def documents(
    s: AsyncSession,
    org_id: UUID,
    *,
    source_type: str | None = None,
    source_id: UUID | None = None,
) -> list[Doc]:
    """The searchable records of an org as text (the newest `SCAN_PER_SOURCE` of each kind), or
    one record when `source_type` + `source_id` are given."""

    def narrowed(stmt: Any, model: Any, kind: str, order: Any) -> Any:
        if source_type is not None and source_type != kind:
            return None
        if source_id is not None:
            return stmt.where(model.id == source_id)
        return stmt.order_by(order.desc()).limit(SCAN_PER_SOURCE)

    docs: list[Doc] = []
    stmt = narrowed(
        select(Finding, Account.name)
        .join(Account, Account.id == Finding.account_id)
        .where(Finding.org_id == org_id),
        Finding, "finding", Finding.last_seen_at,
    )  # fmt: skip
    if stmt is not None:
        found = (await s.execute(stmt)).all()
        evidence = await _evidence(s, org_id, [f.id for f, _ in found])
        docs += [_finding_doc(f, name, evidence.get(f.id, [])) for f, name in found]

    stmt = narrowed(
        select(ActionCard, Account.name)
        .join(Account, Account.id == ActionCard.account_id)
        .where(ActionCard.org_id == org_id),
        ActionCard, "card", ActionCard.created_at,
    )  # fmt: skip
    if stmt is not None:
        docs += [_card_doc(c, name) for c, name in (await s.execute(stmt)).all()]

    # an event that belongs to no account cannot be cited back to one, so it is not indexed
    stmt = narrowed(
        select(Event, Account.name)
        .join(Account, Account.id == Event.account_id)
        .where(Event.org_id == org_id),
        Event, "event", Event.occurred_at,
    )  # fmt: skip
    if stmt is not None:
        docs += [_event_doc(e, name) for e, name in (await s.execute(stmt)).all()]
    return docs


# ------------------------------------------------------------------ indexing
async def pending(s: AsyncSession, org_id: UUID, limit: int, model: str) -> RagPendingOut:
    """Records with no passages yet, or whose text or embedding model changed since."""
    indexed = {
        (kind, sid): (digest, used)
        for kind, sid, digest, used in await s.execute(
            select(
                RagChunk.source_type,
                RagChunk.source_id,
                func.max(RagChunk.content_hash),
                func.max(RagChunk.model),
            )
            .where(RagChunk.org_id == org_id)
            .group_by(RagChunk.source_type, RagChunk.source_id)
        )
    }
    todo = [
        d
        for d in await documents(s, org_id)
        if indexed.get((d.source_type, d.source_id)) != (d.content_hash, model)
    ]
    return RagPendingOut(
        documents=[
            RagDocument(
                source_type=d.source_type,
                source_id=d.source_id,
                account_id=d.account_id,
                account_name=d.account_name,
                title=d.title,
                text=d.text,
                occurred_at=d.occurred_at,
                content_hash=d.content_hash,
            )
            for d in todo[:limit]
        ],
        remaining=max(0, len(todo) - limit),
    )


async def save_chunks(s: AsyncSession, org_id: UUID, body: RagChunksIn) -> RagChunksSavedOut:
    """Replace a record's passages. Whatever the AI service sends is checked against the record
    as it is now: same text version, every passage cut from that text, vectors of the right size."""
    found = await documents(s, org_id, source_type=body.source_type, source_id=body.source_id)
    if not found:
        raise AppError("not_found", "Record not found")
    doc = found[0]
    if doc.content_hash != body.content_hash:
        return RagChunksSavedOut(saved=0, rejected="stale")
    for chunk in body.chunks:
        if chunk.text not in doc.text:
            return RagChunksSavedOut(saved=0, rejected="text_not_in_record")
        if len(chunk.embedding) != EMBEDDING_DIM or not all(map(math.isfinite, chunk.embedding)):
            return RagChunksSavedOut(saved=0, rejected="bad_embedding")
    await s.execute(
        delete(RagChunk).where(
            RagChunk.org_id == org_id,
            RagChunk.source_type == body.source_type,
            RagChunk.source_id == body.source_id,
        )
    )
    s.add_all(
        RagChunk(
            id=new_id(),
            org_id=org_id,
            account_id=doc.account_id,
            source_type=doc.source_type,
            source_id=doc.source_id,
            seq=chunk.seq,
            title=doc.title,
            text=chunk.text,
            content_hash=doc.content_hash,
            occurred_at=doc.occurred_at,
            embedding=chunk.embedding,
            model=body.model,
        )
        for chunk in body.chunks
    )
    await s.flush()
    return RagChunksSavedOut(saved=len(body.chunks))


async def delete_for_sources(
    s: AsyncSession, org_id: UUID, source_type: str, source_ids: list[UUID]
) -> None:
    """Remove the passages of records that are being deleted (e.g. purged mail)."""
    if source_ids:
        await s.execute(
            delete(RagChunk).where(
                RagChunk.org_id == org_id,
                RagChunk.source_type == source_type,
                RagChunk.source_id.in_(source_ids),
            )
        )


# ------------------------------------------------------------------ search
async def has_pgvector(s: AsyncSession) -> bool:
    return bool(
        (await s.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))).scalar()
    )


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


async def search(s: AsyncSession, org_id: UUID, body: RagSearchIn) -> RagSearchOut:
    """The passages closest to a query vector, within this org (and one account, if given)."""
    if len(body.embedding) != EMBEDDING_DIM or not all(map(math.isfinite, body.embedding)):
        raise AppError("validation_error", f"embedding must have {EMBEDDING_DIM} numbers", 422)
    scores: dict[UUID, float]
    if await has_pgvector(s):
        engine = "pgvector"
        # keep walking the index until enough rows pass the tenant / account filter
        await s.execute(text("SET LOCAL hnsw.iterative_scan = 'relaxed_order'"))
        # the same expression as the HNSW index of migration 0009, so the index is used
        distance = "(embedding::vector(768)) <=> CAST(CAST(:q AS text) AS vector(768))"
        scoped = "AND account_id = :account" if body.account_id is not None else ""
        params: dict[str, Any] = {
            "q": "[" + ",".join(repr(float(x)) for x in body.embedding) + "]",
            "org": org_id,
            "model": body.model,
            "k": body.limit,
        }
        if body.account_id is not None:
            params["account"] = body.account_id
        rows = await s.execute(
            text(
                f"SELECT id, 1 - ({distance}) AS score FROM rag_chunks "
                f"WHERE org_id = :org AND model = :model {scoped} "
                f"ORDER BY {distance} LIMIT :k"
            ),
            params,
        )
        scores = {row[0]: float(row[1]) for row in rows}
    else:
        engine = "scan"
        conds = [RagChunk.org_id == org_id, RagChunk.model == body.model]
        if body.account_id is not None:
            conds.append(RagChunk.account_id == body.account_id)
        rows = await s.execute(
            select(RagChunk.id, RagChunk.embedding)
            .where(*conds)
            .order_by(RagChunk.created_at.desc())
            .limit(SCAN_ROWS)
        )
        ranked = sorted(
            ((_cosine(list(vec), body.embedding), cid) for cid, vec in rows), reverse=True
        )
        scores = {cid: score for score, cid in ranked[: body.limit]}

    passages = await passages_by_id(s, org_id, list(scores))
    out = [
        RagPassage(
            id=c.id,
            source_type=c.source_type,
            source_id=c.source_id,
            account_id=c.account_id,
            account_name=name,
            title=c.title,
            occurred_at=c.occurred_at,
            text=c.text,
            score=round(scores[c.id], 4),
        )
        for c, name in passages
    ]
    out.sort(key=lambda p: -p.score)
    return RagSearchOut(passages=out, engine=engine)


async def passages_by_id(
    s: AsyncSession, org_id: UUID, ids: list[UUID]
) -> list[tuple[RagChunk, str | None]]:
    if not ids:
        return []
    rows = await s.execute(
        select(RagChunk, Account.name)
        .outerjoin(Account, Account.id == RagChunk.account_id)
        .where(RagChunk.org_id == org_id, RagChunk.id.in_(ids))
    )
    return [(chunk, name) for chunk, name in rows]


# ------------------------------------------------------------------ the account a question names
async def account_in_question(
    s: AsyncSession, org_id: UUID, question: str
) -> tuple[UUID, str] | None:
    """The one active account whose name (with or without "Corp", "Inc"...) is written in the
    question. None when no account or more than one is named."""
    q = question.lower()
    hits: dict[UUID, tuple[str, str]] = {}  # account -> (longest alias found, name)
    rows = await s.execute(
        select(Account.id, Account.name).where(Account.org_id == org_id, Account.status == "active")
    )
    for account_id, name in rows:
        for alias in {name.lower(), _LEGAL_SUFFIX.sub("", name).lower()}:
            if len(alias) >= 3 and re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", q):
                if len(alias) > len(hits.get(account_id, ("", name))[0]):
                    hits[account_id] = (alias, name)
    # "Acme Labs" also matches an account called "Acme": the longer name is the one meant
    aliases = [alias for alias, _ in hits.values()]
    named = [
        (account_id, name)
        for account_id, (alias, name) in hits.items()
        if not any(alias != other and alias in other for other in aliases)
    ]
    return named[0] if len(named) == 1 else None
