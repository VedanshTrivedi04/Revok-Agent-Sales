"""Typed HTTP client for the backend's service-to-service API (`/internal/v1`, header X-Internal-Key).

Shapes mirror apps/api/app/schemas/internal.py; `tests/unit/test_a7_external.py` validates every request
body against the backend's committed OpenAPI snapshot, so drift fails CI instead of production.
"""

from typing import Any

import httpx
import structlog
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from revops_ai.adapters.backend_contract import BackendProposal
from revops_ai.config import Settings, get_settings
from revops_ai.llm.schemas import Signal

log = structlog.get_logger()


class InternalApiError(Exception):
    def __init__(self, status: int, code: str, message: str = "") -> None:
        super().__init__(f"{status} {code}")
        self.status, self.code, self.message = status, code, message


def _retryable(e: BaseException) -> bool:
    return isinstance(e, httpx.TransportError) or (isinstance(e, InternalApiError) and e.status >= 500 and e.status != 501)  # fmt: skip


class InternalClient:
    def __init__(
        self, settings: Settings | None = None, http: httpx.AsyncClient | None = None
    ) -> None:
        s = settings or get_settings()
        self.base = s.internal_api_url.rstrip("/")
        self.http = http or httpx.AsyncClient(timeout=30.0)
        self.headers = {"X-Internal-Key": s.internal_api_key}

    async def _req(self, method: str, path: str, **kw: Any) -> Any:  # noqa: ANN401
        async for attempt in AsyncRetrying(
            retry=retry_if_exception(_retryable), stop=stop_after_attempt(4),
            wait=wait_exponential_jitter(multiplier=0.2, max=5), reraise=True,
        ):  # fmt: skip
            with attempt:
                r = await self.http.request(
                    method, f"{self.base}{path}", headers=self.headers, **kw
                )
                if r.status_code >= 400:
                    try:
                        err = r.json().get("error", {})
                    except ValueError:
                        err = {}
                    raise InternalApiError(
                        r.status_code, err.get("code", "http_error"), err.get("message", "")
                    )
                return r.json()

    async def _dict(self, method: str, path: str, **kw: Any) -> dict[str, Any]:
        out: dict[str, Any] = await self._req(method, path, **kw)
        return out

    @staticmethod
    def _o(org: str) -> str:
        return f"/v1/orgs/{org}"

    async def context(
        self, org: str, account_id: str, finding_id: str | None = None
    ) -> dict[str, Any]:
        params = {"finding_id": finding_id} if finding_id else None
        return await self._dict(
            "GET", f"{self._o(org)}/accounts/{account_id}/context", params=params
        )

    async def contacts(self, org: str, account_id: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = await self._req(
            "GET", f"{self._o(org)}/accounts/{account_id}/contacts"
        )
        return out

    async def pending(
        self, org: str, limit: int = 25, account_id: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if account_id:
            params["account_id"] = account_id
        return await self._dict("GET", f"{self._o(org)}/events/pending-extraction", params=params)

    async def pending_events(
        self, org: str, limit: int = 25, account_id: str | None = None
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = (await self.pending(org, limit, account_id))["events"]
        return events

    async def save_signals(self, org: str, event_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._dict("POST", f"{self._o(org)}/events/{event_id}/signals", json=body)

    async def save_explanation(
        self, org: str, finding_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._dict(
            "POST", f"{self._o(org)}/findings/{finding_id}/explanation", json=body
        )

    async def save_proposals(
        self, org: str, finding_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._dict(
            "POST", f"{self._o(org)}/findings/{finding_id}/proposals", json=body
        )

    async def run_status(self, org: str, run_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._dict("POST", f"{self._o(org)}/runs/{run_id}/status", json=body)

    # ---- Riddhi's retrieval index: the backend keeps the text and the vectors
    async def rag_pending(self, org: str, model: str, limit: int = 25) -> dict[str, Any]:
        params = {"model": model, "limit": limit}
        return await self._dict("GET", f"{self._o(org)}/rag/pending", params=params)

    async def rag_save_chunks(self, org: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._dict("POST", f"{self._o(org)}/rag/chunks", json=body)

    async def rag_search(self, org: str, body: dict[str, Any]) -> list[dict[str, Any]]:
        out = await self._dict("POST", f"{self._o(org)}/rag/search", json=body)
        passages: list[dict[str, Any]] = out["passages"]
        return passages


# ------------------------------------------------------------------ request body builders
def signals_body(signals: list[Signal], model: str, prompt_version: str) -> dict[str, Any]:
    from revops_ai.adapters.backend_contract import to_backend_signal

    return {"signals": [to_backend_signal(s, model, prompt_version) for s in signals]}


def proposals_body(proposals: list[BackendProposal]) -> dict[str, Any]:
    # `flags` (e.g. contains_internal_metric) travel as their own field: the backend turns the ones
    # it knows into a reviewer note on the card and keeps all of them in the decision log.
    return {
        "proposals": [
            {"type": p.type, "payload": p.payload, "rationale": p.rationale[:500], "evidence_keys": p.evidence_keys, "flags": list(p.flags)}
            for p in proposals
        ]
    }  # fmt: skip
