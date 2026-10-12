"""Client for the AI service (apps/ai), used only when AI_MODE=external.

The backend never sends customer content here: only ids. The AI service reads what it needs from
/internal/v1 and writes results back there, where every input is validated again. Every call in this
module is optional work: when the AI service is off or unreachable the deterministic template
explanation and template cards stay in place.

The one thing sent besides ids is the question a manager typed to Riddhi (`plan_question`): their
own words and the list of questions the backend can answer, never account data.
"""

import time
from typing import Any
from uuid import UUID

import httpx
import structlog

from app.config import get_settings
from app.utils.errors import TransientError

log = structlog.get_logger()
# Planning a question for Riddhi is interactive: wait a bounded time (the AI service's own budget
# is 10 s), and after a failure leave the model alone for a while so every question in that time
# is answered at once by the keyword match.
PLAN_TIMEOUT_S = 12.0
PLAN_PAUSE_S = 60.0
ANSWER_TIMEOUT_S = 50.0  # embedding + search + a few sentences from a small GPU
_plan_paused_until = 0.0  # time.monotonic(); per process


def enabled() -> bool:
    s = get_settings()
    return s.ai_mode == "external" and bool(s.ai_service_url)


def _base() -> str:
    return get_settings().ai_service_url.rstrip("/")


def _headers() -> dict[str, str]:
    return {"X-AI-Key": get_settings().internal_api_key}


async def request_run(
    *, org_id: UUID, account_id: UUID, finding_id: UUID, run_id: UUID, trigger: str
) -> bool:
    """Ask the AI service to explain a finding and draft actions. Raises TransientError when the
    service cannot be reached (the Celery task retries with backoff)."""
    body = {
        "org_id": str(org_id),
        "account_id": str(account_id),
        "finding_id": str(finding_id),
        "run_id": str(run_id),
        "trigger": trigger,
    }
    try:
        async with httpx.AsyncClient(timeout=get_settings().ai_service_timeout_s) as http:
            r = await http.post(f"{_base()}/v1/runs", json=body, headers=_headers())
    except httpx.HTTPError as e:
        raise TransientError("AI service unreachable") from e
    if r.status_code >= 500:
        raise TransientError(f"AI service returned {r.status_code}")
    if r.status_code >= 400:
        log.warning("ai_run_rejected", status=r.status_code, finding_id=str(finding_id))
        return False
    return True


async def request_extraction(
    *, org_id: UUID, account_id: UUID | None = None, limit: int = 25, wait: bool = False
) -> dict[str, Any] | None:
    """Run signal extraction over pending events. Never raises: extraction is best effort and the
    rules run with whatever signals exist."""
    s = get_settings()
    params: dict[str, Any] = {"limit": limit, "wait": str(wait).lower()}
    if account_id is not None:
        params["account_id"] = str(account_id)
    timeout = s.ai_extract_wait_s if wait else s.ai_service_timeout_s
    try:
        async with httpx.AsyncClient(timeout=timeout) as http:
            r = await http.post(
                f"{_base()}/v1/extraction/{org_id}/run", params=params, headers=_headers()
            )
        if r.status_code >= 400:
            log.warning("ai_extraction_rejected", status=r.status_code)
            return None
        out: dict[str, Any] = r.json()
        return out
    except (httpx.HTTPError, ValueError):
        log.warning("ai_extraction_unreachable")
        return None


async def fetch_scores(*, org_id: UUID, account_id: UUID) -> dict[str, Any] | None:
    """Churn and expansion scores of one account from the ML model. None when the service or the
    model is unavailable (the account then simply has no score)."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            r = await http.get(
                f"{_base()}/v1/orgs/{org_id}/accounts/{account_id}/scores", headers=_headers()
            )
    except httpx.HTTPError as e:
        raise TransientError("AI service unreachable") from e
    if r.status_code >= 500 and r.status_code != 503:
        raise TransientError(f"AI service returned {r.status_code}")
    if r.status_code >= 400:  # 503 = models not trained; 4xx = account unknown to the service
        log.warning("ai_scores_unavailable", status=r.status_code)
        return None
    out: dict[str, Any] = r.json()
    return out


async def plan_question(
    *, question: str, questions: list[dict[str, Any]], today: str
) -> dict[str, Any] | None:
    """Which catalog question a question typed to Riddhi means: `{"question_id": id | None, "params"}`.
    None when the service or the model did not answer (the caller then matches by keywords);
    after such a failure it returns None without calling for `PLAN_PAUSE_S`.
    Never raises, and never logs the question."""
    global _plan_paused_until
    if time.monotonic() < _plan_paused_until:
        return None
    body = {"question": question, "questions": questions, "today": today}
    try:
        async with httpx.AsyncClient(timeout=PLAN_TIMEOUT_S) as http:
            r = await http.post(f"{_base()}/v1/assistant/plan", json=body, headers=_headers())
        if r.status_code < 400:
            out = r.json()
            if isinstance(out, dict):
                return out
        log.warning("ai_plan_unavailable", status=r.status_code)
    except (httpx.HTTPError, ValueError):
        log.warning("ai_plan_unreachable")
    _plan_paused_until = time.monotonic() + PLAN_PAUSE_S
    return None


async def answer_question(
    *, org_id: UUID, question: str, account_id: UUID | None, today: str
) -> dict[str, Any] | None:
    """An answer written from the org's indexed records: `{"status": "answered" | "no_evidence",
    "text", "citations": [passage ids]}`. The AI service reads the passages itself through
    /internal/v1; only the typed question and ids are sent. None when it could not answer at all.
    Never raises, and never logs the question."""
    body = {
        "org_id": str(org_id),
        "question": question,
        "account_id": str(account_id) if account_id else None,
        "today": today,
    }
    try:
        async with httpx.AsyncClient(timeout=ANSWER_TIMEOUT_S) as http:
            r = await http.post(f"{_base()}/v1/assistant/answer", json=body, headers=_headers())
        if r.status_code < 400:
            out = r.json()
            if isinstance(out, dict):
                return out
        log.warning("ai_answer_unavailable", status=r.status_code)
    except (httpx.HTTPError, ValueError):
        log.warning("ai_answer_unreachable")
    return None


async def request_indexing(
    *, org_id: UUID, limit: int = 50, wait: bool = False
) -> dict[str, Any] | None:
    """Ask the AI service to embed the org's records that are not searchable yet. Best effort:
    never raises; what is missed now is picked up by the next pass."""
    params: dict[str, str | int] = {"limit": limit, "wait": str(wait).lower()}
    timeout = get_settings().ai_extract_wait_s if wait else get_settings().ai_service_timeout_s
    try:
        async with httpx.AsyncClient(timeout=timeout) as http:
            r = await http.post(
                f"{_base()}/v1/rag/{org_id}/index", params=params, headers=_headers()
            )
        if r.status_code >= 400:
            log.warning("ai_indexing_rejected", status=r.status_code)
            return None
        out: dict[str, Any] = r.json()
        return out
    except (httpx.HTTPError, ValueError):
        log.warning("ai_indexing_unreachable")
        return None


async def health() -> dict[str, Any]:
    """Live status of the AI service and the model behind it (admin LLM health page)."""
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=get_settings().ai_service_timeout_s) as http:
            r = await http.get(f"{_base()}/health", params={"deep": "true"})
        r.raise_for_status()
        data: dict[str, Any] = r.json()
    except (httpx.HTTPError, ValueError):
        return {"ok": False, "llm_ok": False, "model": None, "latency_ms": None}
    data.setdefault("latency_ms", int((time.perf_counter() - started) * 1000))
    return data
