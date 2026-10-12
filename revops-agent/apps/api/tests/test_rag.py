"""Riddhi's retrieval index: what is searchable, that the AI service can only store passages cut
from a tenant's own records, that search never crosses tenants, and that a model-written answer
is shown only with records of this org behind it."""

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.contract import V1
from app.db.session import org_session
from app.models.rag import EMBEDDING_DIM, RagChunk
from app.schemas.internal import RagChunksIn, RagSearchIn
from app.services import ai_client, rag
from tests.factories import (
    AccountFactory,
    CardFactory,
    EventFactory,
    EvidenceFactory,
    FindingFactory,
    persist,
)
from tests.helpers import SeededOrg

MODEL = "test-embed"


def vec(*axes: int) -> list[float]:
    """A unit vector along the given axes: two vectors are close when they share axes."""
    v = [0.0] * EMBEDDING_DIM
    for a in axes:
        v[a] = 1.0 / len(axes) ** 0.5
    return v


async def _seed(org: SeededOrg) -> dict[str, Any]:
    o = org.org_id
    acme = AccountFactory.build(org_id=o, name="Acme Corp", arr=Decimal("84000"))
    globex = AccountFactory.build(org_id=o, name="Globex", arr=Decimal("36000"))
    finding = FindingFactory.build(
        org_id=o,
        account_id=acme.id,
        title="Renewal risk: usage down 38%",
        summary="Usage fell and the champion stopped replying.",
        claims=[{"text": "Active users dropped from 52 to 32.", "evidence_ids": ["E1"]}],
        unknowns=["No product usage data for the last week."],
        priority_score=Decimal("87.4"),
    )
    evidence = EvidenceFactory.build(
        org_id=o, finding_id=finding.id, evidence_key="E1", label="Active users 52 -> 32 (-38%)"
    )
    card = CardFactory.build(
        org_id=o,
        account_id=globex.id,
        type="email_draft",
        tier=2,
        title="Email Globex about adding seats",
        payload={"subject": "More seats for your team", "body_text": "Hi Dana, shall we add 20?"},
    )
    event = EventFactory.build(
        org_id=o, account_id=acme.id, title="Re: Pricing question", body_text="Too expensive."
    )
    orphan = EventFactory.build(org_id=o, account_id=None, title="Unmatched mail")
    await persist(o, acme, globex, finding, evidence, card, event, orphan)
    return {"acme": acme, "globex": globex, "finding": finding, "card": card, "event": event}


async def _index(org_id: UUID, vectors: dict[UUID, list[float]]) -> None:
    """Store one passage per record (the whole text), with the vector given for it."""
    async with org_session(org_id) as s:
        for doc in await rag.documents(s, org_id):
            body = RagChunksIn(
                source_type=doc.source_type,  # type: ignore[arg-type]
                source_id=doc.source_id,
                content_hash=doc.content_hash,
                model=MODEL,
                chunks=[{"seq": 0, "text": doc.text, "embedding": vectors[doc.source_id]}],  # type: ignore[list-item]
            )
            assert (await rag.save_chunks(s, org_id, body)).saved == 1


# --------------------------------------------------------------------- what is searchable
async def test_records_are_rendered_as_text_with_what_a_reader_needs(org_a: SeededOrg) -> None:
    ids = await _seed(org_a)
    async with org_session(org_a.org_id) as s:
        docs = {d.source_id: d for d in await rag.documents(s, org_a.org_id)}
    assert len(docs) == 3  # the event without an account is not indexed

    f = docs[ids["finding"].id]
    assert (f.source_type, f.account_name, f.title) == (
        "finding", "Acme Corp", "Finding: Renewal risk: usage down 38%",
    )  # fmt: skip
    assert f.text.startswith("Risk finding for Acme Corp: Renewal risk: usage down 38%")
    for part in (
        "Priority score: 87.4.",
        "Summary: Usage fell and the champion stopped replying.",
        "- Active users dropped from 52 to 32.",
        "- Active users 52 -> 32 (-38%)",
        "Not confirmed:\n- No product usage data for the last week.",
    ):
        assert part in f.text

    c = docs[ids["card"].id]
    assert "Subject: More seats for your team" in c.text and "Hi Dana, shall we add 20?" in c.text
    e = docs[ids["event"].id]
    assert e.text.endswith("Re: Pricing question\nToo expensive.")


async def test_pending_until_indexed_and_again_when_the_record_or_model_changes(
    org_a: SeededOrg,
) -> None:
    ids = await _seed(org_a)
    o = org_a.org_id
    async with org_session(o) as s:
        page = await rag.pending(s, o, limit=2, model=MODEL)
    assert (len(page.documents), page.remaining) == (2, 1)

    await _index(o, {ids[k].id: vec(i) for i, k in enumerate(("finding", "card", "event"))})
    async with org_session(o) as s:
        assert (await rag.pending(s, o, 25, MODEL)).documents == []
        assert len((await rag.pending(s, o, 25, "another-model")).documents) == 3

        ids["finding"].summary = "The champion replied; usage is recovering."
        await s.merge(ids["finding"])
        await s.flush()
        again = (await rag.pending(s, o, 25, MODEL)).documents
    assert [d.source_id for d in again] == [ids["finding"].id]


@pytest.mark.parametrize(
    ("patch", "reason"),
    [
        ({"content_hash": "0" * 32}, "stale"),
        ({"text": "words that are not in the record"}, "text_not_in_record"),
        ({"embedding": [0.1, 0.2, 0.3]}, "bad_embedding"),
        ({"embedding": [float("nan")] * EMBEDDING_DIM}, "bad_embedding"),
    ],
)
async def test_passages_must_come_from_the_current_record(
    org_a: SeededOrg, patch: dict[str, Any], reason: str
) -> None:
    ids = await _seed(org_a)
    o = org_a.org_id
    async with org_session(o) as s:
        doc = (await rag.documents(s, o, source_type="finding", source_id=ids["finding"].id))[0]
        chunk = {"seq": 0, "text": doc.text[:40], "embedding": vec(1)}
        chunk.update({k: v for k, v in patch.items() if k != "content_hash"})
        body = RagChunksIn.model_construct(
            source_type="finding",
            source_id=doc.source_id,
            content_hash=patch.get("content_hash", doc.content_hash),
            model=MODEL,
            chunks=[type("C", (), chunk)()],
        )
        out = await rag.save_chunks(s, o, body)
    assert (out.saved, out.rejected) == (0, reason)


# --------------------------------------------------------------------- search
async def test_search_ranks_by_similarity_and_stays_inside_the_tenant_and_account(
    org_a: SeededOrg, org_b: SeededOrg
) -> None:
    ids = await _seed(org_a)
    other = await _seed(org_b)
    await _index(org_a.org_id, {ids["finding"].id: vec(1), ids["card"].id: vec(2), ids["event"].id: vec(1, 3)})  # fmt: skip
    await _index(org_b.org_id, {other[k].id: vec(1) for k in ("finding", "card", "event")})

    async with org_session(org_a.org_id) as s:
        out = await rag.search(s, org_a.org_id, RagSearchIn(embedding=vec(1), model=MODEL, limit=5))
        assert out.engine == ("pgvector" if await rag.has_pgvector(s) else "scan")
        assert [p.source_id for p in out.passages] == [
            ids["finding"].id, ids["event"].id, ids["card"].id,
        ]  # fmt: skip
        assert [p.score for p in out.passages] == [1.0, 0.7071, 0.0]
        assert out.passages[0].account_name == "Acme Corp"

        one = await rag.search(
            s,
            org_a.org_id,
            RagSearchIn(embedding=vec(1), model=MODEL, account_id=ids["globex"].id),
        )
        assert [p.source_id for p in one.passages] == [ids["card"].id]
        none = await rag.search(s, org_a.org_id, RagSearchIn(embedding=vec(1), model="other"))
        assert none.passages == []  # vectors of another model are never compared


async def test_purged_records_stop_being_searchable(org_a: SeededOrg) -> None:
    ids = await _seed(org_a)
    o = org_a.org_id
    await _index(o, {ids[k].id: vec(1) for k in ("finding", "card", "event")})
    async with org_session(o) as s:
        await rag.delete_for_sources(s, o, "event", [ids["event"].id])
        out = await rag.search(s, o, RagSearchIn(embedding=vec(1), model=MODEL))
    assert {p.source_type for p in out.passages} == {"finding", "card"}


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("why is Acme at risk", "Acme Corp"),
        ("ACME CORP ke baare me batao", "Acme Corp"),
        ("what did we draft for globex?", "Globex"),
        ("compare Acme and Globex", None),  # two accounts: do not narrow to one
        ("which accounts are at risk", None),
        ("is the acmeplatform down", None),  # part of a longer word is not the account
    ],
)
async def test_the_account_a_question_names(
    org_a: SeededOrg, question: str, expected: str | None
) -> None:
    await _seed(org_a)
    async with org_session(org_a.org_id) as s:
        found = await rag.account_in_question(s, org_a.org_id, question)
    assert (found[1] if found else None) == expected


# --------------------------------------------------------------------- the AI service's endpoints
def _key() -> dict[str, str]:
    return {"X-Internal-Key": get_settings().internal_api_key}


async def test_internal_endpoints_index_and_search_over_http(
    client: AsyncClient, org_a: SeededOrg
) -> None:
    ids = await _seed(org_a)
    base = f"/internal/v1/orgs/{org_a.org_id}/rag"
    assert (await client.get(f"{base}/pending", params={"model": MODEL})).status_code == 401

    page = (await client.get(f"{base}/pending", params={"model": MODEL}, headers=_key())).json()
    assert {d["source_type"] for d in page["documents"]} == {"finding", "card", "event"}
    for i, doc in enumerate(page["documents"]):
        saved = await client.post(
            f"{base}/chunks",
            headers=_key(),
            json={
                "source_type": doc["source_type"],
                "source_id": doc["source_id"],
                "content_hash": doc["content_hash"],
                "model": MODEL,
                "chunks": [{"seq": 0, "text": doc["text"][:60], "embedding": vec(i)}],
            },
        )
        assert saved.status_code == 200 and saved.json() == {"saved": 1, "rejected": None}
    again = await client.get(f"{base}/pending", params={"model": MODEL}, headers=_key())
    assert again.json()["documents"] == []

    found = await client.post(
        f"{base}/search", headers=_key(), json={"embedding": vec(0), "model": MODEL, "limit": 1}
    )
    assert found.status_code == 200
    top = found.json()["passages"][0]
    assert top["source_id"] == page["documents"][0]["source_id"] and top["score"] == 1.0

    bad = await client.post(
        f"{base}/search", headers=_key(), json={"embedding": [1.0, 2.0], "model": MODEL}
    )
    assert bad.status_code == 422
    missing = await client.post(
        f"{base}/chunks",
        headers=_key(),
        json={"source_type": "finding", "source_id": str(uuid4()), "content_hash": "x", "model": MODEL, "chunks": []},
    )  # fmt: skip
    assert missing.status_code == 404
    assert ids["finding"].id  # seeded


# --------------------------------------------------------------------- Riddhi answering from records
class _AI:
    """The AI service, scripted: which question the planner picks and what the answer step says."""

    def __init__(self) -> None:
        self.answer: dict[str, Any] | None = None
        self.asked: list[dict[str, Any]] = []

    async def plan_question(self, **_: Any) -> dict[str, Any]:
        return {"question_id": "search_records", "params": {}}

    async def answer_question(self, **kwargs: Any) -> dict[str, Any] | None:
        self.asked.append(kwargs)
        return self.answer


@pytest.fixture
def ai(monkeypatch: pytest.MonkeyPatch) -> _AI:
    fake = _AI()
    monkeypatch.setattr(ai_client, "enabled", lambda: True)
    monkeypatch.setattr(ai_client, "plan_question", fake.plan_question)
    monkeypatch.setattr(ai_client, "answer_question", fake.answer_question)
    return fake


async def _chunk_ids(org_id: UUID) -> dict[UUID, UUID]:
    from sqlalchemy import select

    async with org_session(org_id) as s:
        rows = await s.execute(select(RagChunk.source_id, RagChunk.id))
        return {source: chunk for source, chunk in rows}


async def _ask(client: AsyncClient, question: str) -> Any:
    r = await client.post(f"{V1}/assistant/ask", json={"question": question})
    assert r.status_code == 200, r.text
    return r.json()


async def test_an_answer_from_records_is_shown_with_the_records_it_cites(
    client_as: Any, org_a: SeededOrg, ai: _AI
) -> None:
    ids = await _seed(org_a)
    await _index(org_a.org_id, {ids[k].id: vec(1) for k in ("finding", "card", "event")})
    chunks = await _chunk_ids(org_a.org_id)
    ai.answer = {
        "status": "answered",
        "text": "Acme Corp is at risk because active users dropped from 52 to 32.",
        "citations": [str(chunks[ids["finding"].id]), str(chunks[ids["event"].id]), "not-a-uuid"],
    }
    data = await _ask(client_as("manager"), "Acme risk me kyun hai?")

    assert (data["status"], data["question_id"], data["generated"]) == (
        "answered", "search_records", True,
    )  # fmt: skip
    assert data["text"] == "Acme Corp is at risk because active users dropped from 52 to 32."
    assert data["basis"].startswith("Written by the model from the 2 records below")
    assert data["basis"].endswith("timeline events of Acme Corp.")
    finding_row, event_row = data["rows"]
    assert finding_row["title"] == "Finding: Renewal risk: usage down 38%"
    assert finding_row["finding_id"] == str(ids["finding"].id)
    assert finding_row["detail"].startswith("Acme Corp · Risk finding for Acme Corp")
    assert (event_row["finding_id"], event_row["account_id"]) == (None, str(ids["acme"].id))
    # only the typed question and ids went to the AI service; the account was resolved here
    assert ai.asked[0]["account_id"] == ids["acme"].id
    assert ai.asked[0]["question"] == "Acme risk me kyun hai?"


async def test_model_text_without_this_orgs_records_behind_it_is_never_shown(
    client_as: Any, org_a: SeededOrg, org_b: SeededOrg, ai: _AI
) -> None:
    await _seed(org_a)
    other = await _seed(org_b)
    await _index(org_b.org_id, {other[k].id: vec(1) for k in ("finding", "card", "event")})
    foreign = await _chunk_ids(org_b.org_id)

    for answer in (
        {"status": "answered", "text": "A confident sentence.", "citations": []},
        {"status": "answered", "text": "From another tenant.", "citations": [str(foreign[other["finding"].id])]},
        {"status": "no_evidence", "text": "", "citations": []},
    ):  # fmt: skip
        ai.answer = answer
        data = await _ask(client_as("manager"), "what did the customer say about pricing")
        assert (data["status"], data["rows"], data["generated"]) == ("not_found", [], False)
        assert data["text"] == "Riddhi found nothing in the records that answers this."

    ai.answer = None  # AI service unreachable
    data = await _ask(client_as("manager"), "what did the customer say about pricing")
    assert data["status"] == "unsupported" and "could not read the records" in data["text"]
    assert data["suggestions"]
