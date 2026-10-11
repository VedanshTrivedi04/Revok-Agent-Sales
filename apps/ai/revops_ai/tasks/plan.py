"""Riddhi (the workspace assistant): a typed question -> one question of the backend's catalog and its numbers.

The model never answers the question and never sees customer records: it gets the manager's own
words and the list of questions the backend can compute, and returns an id plus up to three
numbers. The backend checks the id and clamps the numbers again before it runs anything.

Never raises: on model failure it returns `failed=True` and the backend falls back to its keyword
match. A person is waiting for this answer, so the whole call has a short time budget.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import date

import structlog
from pydantic import BaseModel, Field

from revops_ai.llm import prompts
from revops_ai.llm.client import CallMeta, LLMClient, LLMOutputError
from revops_ai.llm.schemas import PlanOutput

log = structlog.get_logger()
MAX_CHARS = 500
# For all attempts together; past it the backend's keyword match is the better answer.
BUDGET_S = 6.0
NUMBERS = ("min_score", "days", "limit")


class CatalogQuestion(BaseModel):
    """One question the backend can answer, and which numbers it takes."""

    id: str = Field(min_length=1, max_length=64)
    text: str = Field(max_length=300)
    params: list[str] = Field(default_factory=list, max_length=8)


@dataclass
class PlanResult:
    question_id: str | None = None  # None = the question matches nothing in the catalog
    params: dict[str, int] = field(default_factory=dict)
    failed: bool = False
    prompt_version: str = ""
    model: str = ""
    metas: list[CallMeta] = field(default_factory=list)


async def plan_question(
    llm: LLMClient,
    *,
    question: str,
    questions: list[CatalogQuestion],
    today: date,
    prompt_version: str | None = None,
) -> PlanResult:
    p = prompts.load("plan", prompt_version)
    res = PlanResult(prompt_version=p.tag)
    text = " ".join(question.split())[:MAX_CHARS]
    if not text or not questions:
        return res

    messages = p.render(today=today.isoformat(), questions=questions, question=text)
    out: PlanOutput | None = None
    try:
        async with asyncio.timeout(BUDGET_S):
            for attempt in range(2):  # one retry on invalid output
                try:
                    out, meta = await llm.call_json("plan", messages, PlanOutput, temperature=0.0, max_tokens=120)  # fmt: skip
                    res.metas.append(meta)
                    res.model = meta.model
                    break
                except LLMOutputError:
                    log.warning("plan_invalid_output", attempt=attempt)
    except TimeoutError:
        log.warning("plan_timed_out", budget_s=BUDGET_S)
    except Exception as e:  # noqa: BLE001 - the client already retried; never reach the caller
        log.warning("plan_call_failed", error_type=type(e).__name__)
    if out is None:
        res.failed = True
        return res

    chosen = next((q for q in questions if q.id == out.question_id.strip()), None)
    if chosen is None:  # "none", or an id that is not in the list: nothing to answer
        return res
    res.question_id = chosen.id
    for key in NUMBERS:
        value = getattr(out, key)
        if value is not None and key in chosen.params:
            res.params[key] = value
    return res
