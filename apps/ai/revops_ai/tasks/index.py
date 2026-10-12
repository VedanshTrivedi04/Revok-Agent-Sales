"""Riddhi's retrieval index: cut the backend's pending records into passages and embed them.

The backend renders each record (a finding, an action card, a timeline event) to text and keeps
the passages and vectors; this side only cuts and embeds. A passage is always an exact substring
of the record's text, because the backend checks that before it stores anything.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

import structlog

from revops_ai.llm.embeddings import Embedder

log = structlog.get_logger()
CHUNK_CHARS = 900
OVERLAP = 120
MAX_CHUNKS = 40
_BREAKS = ("\n\n", "\n", ". ", "; ", " ")


class IndexBackend(Protocol):
    async def rag_pending(self, org: str, model: str, limit: int = 25) -> dict[str, Any]: ...

    async def rag_save_chunks(self, org: str, body: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class IndexReport:
    processed: int = 0  # records
    saved: int = 0  # passages
    failed: int = 0  # records the embedding endpoint could not embed (retried on the next pass)
    rejected: list[dict[str, str]] = field(default_factory=list)
    remaining: int = 0  # records still waiting after this page


def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = OVERLAP) -> list[str]:
    """Passages of at most `size` characters, cut at paragraph, line or sentence ends where one
    falls in the second half of the window. Each passage is an exact substring of `text`."""
    chunks: list[str] = []
    start, n = 0, len(text)
    while start < n:
        end = min(n, start + size)
        if end < n:
            window = text[start:end]
            for mark in _BREAKS:
                cut = window.rfind(mark, size // 2)
                if cut != -1:
                    end = start + cut + len(mark)
                    break
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
        space = text.find(" ", start, end)  # do not begin in the middle of a word
        if space != -1:
            start = space + 1
    return chunks


async def index_pending(
    embedder: Embedder, client: IndexBackend, org_id: str, *, limit: int = 25
) -> IndexReport:
    page = await client.rag_pending(org_id, embedder.model, limit)
    rep = IndexReport(remaining=int(page.get("remaining", 0)))
    for doc in page["documents"]:
        rep.processed += 1
        chunks = chunk_text(doc["text"])[:MAX_CHUNKS]
        try:
            # later passages lose the record's first line, so the title goes into what is embedded
            vectors = await embedder.embed_documents(
                [c if i == 0 else f"{doc['title']}\n{c}" for i, c in enumerate(chunks)]
            )
        except Exception as e:  # noqa: BLE001 - one record must not stop the pass
            log.warning("index_embed_failed", error_type=type(e).__name__)
            rep.failed += 1
            continue
        out = await client.rag_save_chunks(
            org_id,
            {
                "source_type": doc["source_type"],
                "source_id": doc["source_id"],
                "content_hash": doc["content_hash"],
                "model": embedder.model,
                "chunks": [
                    {"seq": i, "text": c, "embedding": v}
                    for i, (c, v) in enumerate(zip(chunks, vectors, strict=True))
                ],
            },
        )
        rep.saved += int(out.get("saved", 0))
        if out.get("rejected"):
            rep.rejected.append({"source_id": str(doc["source_id"]), "reason": out["rejected"]})
    return rep
