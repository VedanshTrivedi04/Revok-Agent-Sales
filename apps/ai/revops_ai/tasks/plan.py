"""Riddhi (the workspace assistant): a typed question -> one question of the backend's catalog
and its numbers.

The model never answers the question and never sees customer records: it gets the manager's own
words and the list of questions the backend can compute, and returns an id plus up to three
numbers. The backend checks the id and clamps the numbers again before it runs anything.

Never raises: on model failure it returns `failed=True` and the backend falls back to its keyword
match. A person is waiting for this answer, so the whole call has a short time budget.
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import date

import structlog
from pydantic import BaseModel, Field

from revops_ai.llm import prompts
from revops_ai.llm.client import CallMeta, LLMClient, LLMOutputError
from revops_ai.llm.schemas import PlanOutput
from revops_ai.validation.injection import find_injections

log = structlog.get_logger()
MAX_CHARS = 500
# For all attempts together; past it the backend's keyword match is the better answer. A small
# GPU needs 2-4 s per question, and longer for the first one after it was idle.
BUDGET_S = 10.0
NUMBERS = ("min_score", "days", "limit")
# A threshold or a row count is only ever copied from the question, never worked out, so the
# digits must be there. `days` is exempt: "two weeks" and "is mahine" are periods without digits.
QUOTED_NUMBERS = ("min_score", "limit")


class CatalogQuestion(BaseModel):
    """One question the backend can answer, and which numbers it takes."""

    id: str = Field(min_length=1, max_length=64)
    text: str = Field(max_length=300)
    about: str = Field(default="", max_length=400)  # what it covers, in other words
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
    if _steers_the_planner(text, questions):
        log.warning("plan_instruction_refused")
        return res

    messages = p.render(today=today.isoformat(), questions=questions, question=text)
    out: PlanOutput | None = None
    try:
        async with asyncio.timeout(BUDGET_S):
            for attempt in range(2):  # one retry on invalid output
                try:
                    out, meta = await llm.call_json("plan", messages, PlanOutput, temperature=0.0, max_tokens=160)  # fmt: skip
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
        if value is None or key not in chosen.params:
            continue
        if key in QUOTED_NUMBERS and not re.search(rf"(?<!\d){value}(?!\d)", text):
            continue  # a number the manager did not write (usually a default copied from the list)
        res.params[key] = value
    return res


def _steers_the_planner(text: str, questions: list[CatalogQuestion]) -> bool:
    """Text that tries to dictate the output: instruction-like sentences, or the planner's own
    vocabulary (`question_id`, a catalog id). Decided in code, so it does not depend on the model
    noticing; the answer is then "none of the questions"."""
    lowered = text.lower()
    if "question_id" in lowered or any(q.id.lower() in lowered for q in questions if "_" in q.id):
        return True
    return bool(find_injections(text))
