"""Worker loop pieces for external mode: T1 over the backend's pending-extraction queue."""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from revops_ai.adapters.internal_client import InternalClient, signals_body
from revops_ai.llm.client import LLMClient
from revops_ai.tasks.extract import extract_signals

log = structlog.get_logger()


@dataclass
class ExtractionReport:
    processed: int = 0
    saved: int = 0
    rejected: list[dict[str, Any]] = field(default_factory=list)
    failed: int = 0
    quarantined: int = 0


async def extract_pending(llm: LLMClient, client: InternalClient, org_id: str, *, limit: int = 25, concurrency: int = 4, org_name: str | None = None, prompt_version: str | None = None, account_id: str | None = None) -> ExtractionReport:  # fmt: skip
    """Pull events with signals_extracted_at IS NULL, run T1, save signals (backend validates quotes).

    Events with no signals are still POSTed with an empty list so the backend marks them extracted and
    they are not fetched again. Failed extractions are NOT marked, so they are retried on the next pass.
    """
    page = await client.pending(org_id, limit, account_id)
    events = page["events"]
    our_name = org_name or page.get("org_name") or "our company"
    rep = ExtractionReport()
    sem = asyncio.Semaphore(concurrency)

    async def one(e: dict[str, Any]) -> None:
        async with sem:
            r = await extract_signals(
                llm, text=e.get("text", ""), org_name=our_name, account_name=e.get("account_name") or "Account",
                date=datetime.fromisoformat(str(e["occurred_at"]).replace("Z", "+00:00")) if e.get("occurred_at") else datetime.now(UTC),
                inbound=e.get("type") != "email_out", prompt_version=prompt_version,
            )  # fmt: skip
            rep.processed += 1
            rep.quarantined += r.quarantined
            if r.failed:
                rep.failed += 1
                return
            if r.skipped and not e.get("text", "").strip():
                pass  # nothing to extract: mark as extracted with no signals
            out = await client.save_signals(
                org_id,
                str(e["id"]),
                signals_body(r.signals, r.model or "unknown", r.prompt_version),
            )
            rep.saved += int(out.get("saved", 0))
            rep.rejected += list(out.get("rejected", []))

    await asyncio.gather(*(one(e) for e in events))
    return rep
