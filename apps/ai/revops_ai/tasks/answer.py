"""Riddhi: answer a question from the workspace's own records (retrieval, then a cited answer).

Flow: embed the question -> the backend's similarity search (inside the tenant, optionally one
account) -> the model writes a short answer from those passages only -> code checks it. An answer
is returned only when it cites passages that were really given and every number and date in it
appears in a cited passage. Anything else is "no_evidence": Riddhi then says it found nothing,
which is better than an unsupported sentence.

Never raises. A person is waiting, so the whole call has a time budget.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, Protocol

import structlog

from revops_ai.llm import prompts
from revops_ai.llm.client import CallMeta, LLMClient, LLMOutputError
from revops_ai.llm.embeddings import Embedder
from revops_ai.llm.schemas import AnswerOutput
from revops_ai.validation.injection import redact, scan
from revops_ai.validation.numbers import unsupported_facts

log = structlog.get_logger()
MAX_CHARS = 500
SEARCH_LIMIT = 8
MAX_PASSAGES = 6
PASSAGE_CHARS = 900
MIN_SCORE = 0.2  # cosine similarity below this is noise for any embedding model we use
BUDGET_S = 40.0


class SearchBackend(Protocol):
    async def rag_search(self, org: str, body: dict[str, Any]) -> list[dict[str, Any]]: ...


@dataclass
class AnswerResult:
    status: Literal["answered", "no_evidence", "failed"] = "failed"
    text: str = ""
    citations: list[str] = field(default_factory=list)  # ids of the backend's passages
    prompt_version: str = ""
    model: str = ""
    passages: int = 0  # how many passages the model was shown
    metas: list[CallMeta] = field(default_factory=list)


def _safe(text: str) -> str:
    """A passage as the model may see it: instruction-like sentences are cut out first."""
    work, hits = scan(text)
    return redact(work, hits)[:PASSAGE_CHARS]


async def answer_question(
    llm: LLMClient,
    embedder: Embedder,
    client: SearchBackend,
    *,
    org_id: str,
    question: str,
    account_id: str | None = None,
    today: date,
    prompt_version: str | None = None,
) -> AnswerResult:
    p = prompts.load("answer", prompt_version)
    res = AnswerResult(prompt_version=p.tag)
    text = " ".join(question.split())[:MAX_CHARS]
    if not text:
        res.status = "no_evidence"
        return res
    try:
        async with asyncio.timeout(BUDGET_S):
            await _answer(llm, embedder, client, res, p, org_id, text, account_id, today)
    except TimeoutError:
        log.warning("answer_timed_out", budget_s=BUDGET_S)
        res.status = "failed"
    except Exception as e:  # noqa: BLE001 - search, embedding or model down: never reach the caller
        log.warning("answer_failed", error_type=type(e).__name__)
        res.status = "failed"
    return res


async def _answer(
    llm: LLMClient,
    embedder: Embedder,
    client: SearchBackend,
    res: AnswerResult,
    p: prompts.Prompt,
    org_id: str,
    text: str,
    account_id: str | None,
    today: date,
) -> None:
    body: dict[str, Any] = {
        "embedding": await embedder.embed_query(text),
        "model": embedder.model,
        "limit": SEARCH_LIMIT,
    }
    if account_id:
        body["account_id"] = account_id
    found = [f for f in await client.rag_search(org_id, body) if f["score"] >= MIN_SCORE]
    by_key = {f"P{i}": f for i, f in enumerate(found[:MAX_PASSAGES], 1)}
    res.passages = len(by_key)
    if not by_key:
        res.status = "no_evidence"
        return

    messages = p.render(
        today=today.isoformat(),
        question=text,
        passages=[
            {
                "key": key,
                "title": f["title"],
                "account": f.get("account_name"),
                "text": _safe(f["text"]),
            }
            for key, f in by_key.items()
        ],
    )
    for attempt in range(2):  # one retry, with the exact problem, on an ungrounded answer
        try:
            out, meta = await llm.call_json("answer", messages, AnswerOutput, temperature=0.1, max_tokens=400)  # fmt: skip
        except LLMOutputError:
            log.warning("answer_invalid_output", attempt=attempt)
            messages = messages + [{"role": "user", "content": "Your previous answer was not valid JSON for the required keys. Return JSON only."}]  # fmt: skip
            continue
        res.metas.append(meta)
        res.model = meta.model
        if not out.answerable or not out.answer.strip():
            res.status = "no_evidence"
            return
        cited = [c for c in dict.fromkeys(c.strip() for c in out.citations) if c in by_key]
        if not cited:
            problem = "you cited no passage id from the list"
        else:
            # checked against what was stored (title and text), not the redacted copy
            missing = unsupported_facts(
                out.answer, [f"{by_key[c]['title']}\n{by_key[c]['text']}" for c in cited]
            )
            problem = f"not found in the passages you cited: {', '.join(missing[:4])}" if missing else ""  # fmt: skip
        if not problem:
            res.status = "answered"
            res.text = out.answer.strip()
            res.citations = [str(by_key[c]["id"]) for c in cited]
            return
        log.warning("answer_not_grounded", attempt=attempt)
        messages = messages + [
            {"role": "assistant", "content": out.model_dump_json()},
            {"role": "user", "content": f"Problem with your answer: {problem}. Use only the passages, copy numbers and dates exactly, and cite the passage ids you used. If the passages do not answer the question, return answerable false. Return JSON only."},
        ]  # fmt: skip
    res.status = (
        "no_evidence"  # two ungrounded attempts: say nothing rather than something unsupported
    )
