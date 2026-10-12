"""AI service HTTP API: how the backend (or an operator) triggers runs.

    POST /v1/runs                      {org_id, account_id, finding_id, run_id?, trigger}  -> 202 {run_id}
    GET  /v1/runs/{run_id}                                                        -> state summary
    POST /v1/runs/{run_id}/resume      {decisions: {card_id: approved|rejected|expired}}
    POST /v1/extraction/{org_id}/run   ?account_id=&limit=&wait=                  -> T1 over pending events
    POST /v1/assistant/plan            {question, questions[], today?}            -> {question_id, params}
    POST /v1/assistant/answer          {org_id, question, account_id?, today?}    -> {status, text, citations[]}
    POST /v1/rag/{org_id}/index        ?limit=&wait=                              -> embed pending records
    GET  /health                       ?deep=true also probes the model endpoint

Auth: header `X-AI-Key`. The service never accepts customer content: only ids. Everything it needs it
reads from the backend's /internal/v1. The one exception is /v1/assistant/plan, which receives the
question a signed-in manager typed (their own words, not stored customer records) and the list of
questions the backend can answer; it returns which one fits, and nothing is stored or logged.
/v1/assistant/answer takes the typed question and ids too: the passages it answers from are read
from the backend's /internal/v1 search, like everything else.

Runs are queued, never refused: one run at a time per account (a risk and an expansion finding of the
same account run one after the other) and `max_concurrent_runs` in flight overall, so a nightly fan-out
from the backend cannot overload the model endpoint.
"""

import asyncio
import hmac
import time
import uuid
from datetime import date
from typing import Annotated, Any, Literal

import httpx
import structlog
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from revops_ai.adapters.external import InternalApiBackend, InternalApiProvider
from revops_ai.adapters.internal_client import InternalClient
from revops_ai.config import Settings, get_settings
from revops_ai.graph.graph import Deps
from revops_ai.graph.runner import AccountRunner
from revops_ai.llm.client import LLMClient
from revops_ai.llm.embeddings import Embedder, OpenAICompatEmbedder
from revops_ai.observability.tracing import Sink
from revops_ai.observability.versions import select_prompts
from revops_ai.tasks.answer import answer_question
from revops_ai.tasks.index import index_pending
from revops_ai.tasks.plan import CatalogQuestion, plan_question
from revops_ai.worker import extract_pending

log = structlog.get_logger()
MAX_REMEMBERED_RUNS = 2000
HEALTH_TTL_S = 30.0


class StartRun(BaseModel):
    org_id: str
    account_id: str
    finding_id: str
    run_id: str | None = None  # the backend's agent_runs.id; status reports are posted to it
    trigger: Literal["nightly", "manual", "webhook", "retry"] = "manual"


class Resume(BaseModel):
    decisions: dict[str, Literal["approved", "rejected", "expired"]]


class PlanRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    questions: list[CatalogQuestion] = Field(min_length=1, max_length=50)
    today: date | None = None  # the backend's "today" (UTC); defaults to this host's date


class AnswerRequest(BaseModel):
    org_id: str
    question: str = Field(min_length=1, max_length=500)
    account_id: str | None = None  # the account the question names, resolved by the backend
    today: date | None = None


def _summary(st: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": st.get("status"), "error": st.get("error"), "rule_hits": st.get("rule_hits"),
        "card_ids": st.get("card_ids"), "used_fallback": st.get("used_fallback"), "versions": st.get("versions"),
    }  # fmt: skip


def create_service(
    llm: LLMClient,
    client: InternalClient,
    saver: Any = None,
    *,
    api_key: str | None = None,
    settings: Settings | None = None,
    sink: Sink | None = None,
    wait_for_approval: bool | None = None,
    embedder: Embedder | None = None,
) -> FastAPI:
    cfg = settings or get_settings()
    embed = embedder or OpenAICompatEmbedder(cfg)
    key = api_key or cfg.ai_service_key or cfg.internal_api_key
    wait = cfg.ai_wait_for_approval if wait_for_approval is None else wait_for_approval
    app = FastAPI(title="RevOps AI service", version="0.2.0")
    provider = InternalApiProvider(client)
    deps = Deps(
        llm=llm,
        provider=provider,
        backend=InternalApiBackend(client),
        prompts=select_prompts("default"),
        sink=sink,
        wait_for_approval=wait,
    )
    runner = AccountRunner(deps, saver)
    tasks: dict[str, asyncio.Task[Any]] = {}
    results: dict[str, dict[str, Any]] = {}  # run_id -> summary of a finished run
    active: dict[tuple[str, str], str] = {}  # (org_id, finding_id) -> run_id queued or running
    locks: dict[str, asyncio.Lock] = {}
    extract_locks: dict[str, asyncio.Lock] = {}
    index_locks: dict[str, asyncio.Lock] = {}
    slots = asyncio.Semaphore(max(1, cfg.ai_max_concurrent_runs))
    llm_health: dict[str, Any] = {"at": 0.0, "data": {}}

    async def auth(x_ai_key: Annotated[str | None, Header()] = None) -> None:
        if not x_ai_key or not hmac.compare_digest(x_ai_key, key):
            raise HTTPException(401, "missing or invalid X-AI-Key")

    async def _probe_llm() -> dict[str, Any]:
        """Is the model endpoint answering? Cached briefly: this backs an admin page, not a hot path."""
        if time.monotonic() - llm_health["at"] < HEALTH_TTL_S and llm_health["data"]:
            return dict(llm_health["data"])
        started = time.perf_counter()
        ok = False
        try:
            async with httpx.AsyncClient(timeout=8.0) as http:
                r = await http.get(
                    f"{cfg.llm_base_url.rstrip('/')}/models",
                    headers={"Authorization": f"Bearer {cfg.llm_api_key}"},
                )
            ok = r.status_code == 200
        except httpx.HTTPError:
            ok = False
        data = {"llm_ok": ok, "llm_latency_ms": int((time.perf_counter() - started) * 1000) if ok else None}  # fmt: skip
        llm_health.update(at=time.monotonic(), data=data)
        return dict(data)

    @app.get("/health")
    async def health(deep: bool = False) -> dict[str, Any]:
        out: dict[str, Any] = {
            "ok": True,
            "mode": "external",
            "model": cfg.llm_model,
            "prompt_versions": dict(deps.prompts.versions) if deps.prompts else {},
            "active_runs": sum(1 for t in tasks.values() if not t.done()),
        }
        if deep:
            out.update(await _probe_llm())
        return out

    def _forget_old() -> None:
        for rid in [r for r, t in tasks.items() if t.done()]:
            tasks.pop(rid, None)
        while len(results) > MAX_REMEMBERED_RUNS:
            results.pop(next(iter(results)))

    @app.post("/v1/runs", status_code=202, dependencies=[Depends(auth)])
    async def start(body: StartRun) -> dict[str, str]:
        same = active.get((body.org_id, body.finding_id))
        if (
            same is not None
        ):  # the same finding is already queued or running: do not explain it twice
            return {"run_id": same, "status": "already_running"}
        run_id = body.run_id or str(uuid.uuid4())
        # two findings of one account may share the backend run id; keep our thread ids distinct
        thread_id = f"{run_id}:{body.finding_id}"
        lock = locks.setdefault(f"{body.org_id}:{body.account_id}", asyncio.Lock())
        active[(body.org_id, body.finding_id)] = thread_id

        async def go() -> None:
            try:
                async with lock, slots:
                    provider.finding_ids[body.account_id] = body.finding_id
                    try:
                        st = await runner.run(body.org_id, body.account_id, run_id, body.trigger, thread_id=thread_id)  # fmt: skip
                    finally:
                        provider.forget(body.account_id)
                    results[thread_id] = _summary(dict(st))
                    if st.get("status") != "waiting_approval":
                        await runner.forget(thread_id, run_id)
            except Exception as e:  # noqa: BLE001 - a crashed run must not take the service down
                log.error("run_crashed", exc_type=type(e).__name__)
                results[thread_id] = {"status": "failed", "error": type(e).__name__}
            finally:
                active.pop((body.org_id, body.finding_id), None)

        _forget_old()
        tasks[thread_id] = asyncio.create_task(go())
        return {"run_id": thread_id, "status": "queued"}

    @app.get("/v1/runs/{run_id}", dependencies=[Depends(auth)])
    async def get_run(run_id: str) -> dict[str, Any]:
        if run_id in results:
            return {"run_id": run_id, **results[run_id]}
        if run_id in tasks:
            return {"run_id": run_id, "status": "running"}
        raise HTTPException(404, "unknown run")

    @app.post("/v1/runs/{run_id}/resume", dependencies=[Depends(auth)])
    async def resume(run_id: str, body: Resume) -> dict[str, Any]:
        if results.get(run_id, {}).get("status") != "waiting_approval":
            raise HTTPException(404, "no run is waiting for approval under this id")
        st = await runner.resume(run_id, dict(body.decisions))
        results[run_id] = _summary(dict(st))
        return {"run_id": run_id, "status": st.get("status")}

    @app.post("/v1/extraction/{org_id}/run", dependencies=[Depends(auth)])
    async def extraction(org_id: str, limit: int = 25, account_id: str | None = None, wait: bool = True) -> dict[str, Any]:  # fmt: skip
        """T1 over the pending events of an org (optionally one account). `wait=false` returns at
        once and extracts in the background; a second request for the same scope is not doubled."""
        scope = f"{org_id}:{account_id or '*'}"
        lock = extract_locks.setdefault(scope, asyncio.Lock())

        async def go() -> dict[str, Any]:
            async with lock:
                r = await extract_pending(llm, client, org_id, limit=limit, account_id=account_id, prompt_version=deps.pv("extract"))  # fmt: skip
            return {"processed": r.processed, "saved": r.saved, "failed": r.failed, "quarantined": r.quarantined, "rejected": len(r.rejected)}  # fmt: skip

        if wait:
            return await go()
        if lock.locked():
            return {"status": "already_running"}

        async def background() -> None:
            try:
                await go()
            except Exception as e:  # noqa: BLE001
                log.error("extraction_crashed", exc_type=type(e).__name__)

        tasks[f"extract:{scope}:{uuid.uuid4()}"] = asyncio.create_task(background())
        _forget_old()
        return {"status": "started"}

    @app.post("/v1/assistant/plan", dependencies=[Depends(auth)])
    async def assistant_plan(body: PlanRequest) -> dict[str, Any]:
        """Which catalog question a typed question means. `question_id: null` = none of them."""
        r = await plan_question(
            llm, question=body.question, questions=body.questions, today=body.today or date.today()
        )
        if r.failed:  # the caller falls back to its own keyword match
            raise HTTPException(503, "the model did not return a plan")
        return {
            "question_id": r.question_id,
            "params": r.params,
            "model": r.model,
            "prompt_version": r.prompt_version,
        }

    @app.post("/v1/assistant/answer", dependencies=[Depends(auth)])
    async def assistant_answer(body: AnswerRequest) -> dict[str, Any]:
        """An answer written from the org's own records, with the passages it relies on.
        `no_evidence` = nothing in the records answers it."""
        r = await answer_question(
            llm, embed, client, org_id=body.org_id, question=body.question,
            account_id=body.account_id, today=body.today or date.today(),
        )  # fmt: skip
        if r.status == "failed":  # search, embedding or model unavailable
            raise HTTPException(503, "could not read the records")
        return {
            "status": r.status,
            "text": r.text,
            "citations": r.citations,
            "model": r.model,
            "prompt_version": r.prompt_version,
        }

    @app.post("/v1/rag/{org_id}/index", dependencies=[Depends(auth)])
    async def rag_index(org_id: str, limit: int = 25, wait: bool = True) -> dict[str, Any]:
        """Embed the org's records that are not in the retrieval index yet (or changed since).
        `wait=false` returns at once; a second request for the same org is not doubled."""
        lock = index_locks.setdefault(org_id, asyncio.Lock())

        async def go() -> dict[str, Any]:
            async with lock:
                r = await index_pending(embed, client, org_id, limit=limit)
            return {"processed": r.processed, "saved": r.saved, "failed": r.failed, "rejected": len(r.rejected), "remaining": r.remaining}  # fmt: skip

        if wait:
            return await go()
        if lock.locked():
            return {"status": "already_running"}

        async def background() -> None:
            try:
                await go()
            except Exception as e:  # noqa: BLE001
                log.error("indexing_crashed", exc_type=type(e).__name__)

        tasks[f"index:{org_id}:{uuid.uuid4()}"] = asyncio.create_task(background())
        _forget_old()
        return {"status": "started"}

    async def _scores(org_id: str, account_id: str) -> dict[str, Any]:
        from revops_ai.adapters.external import fixture_from_context
        from revops_ai.ml.features import features_from_fixture
        from revops_ai.ml.scoring import Scorer, combined_view

        missing = [t for t in ("churn", "expansion") if not Scorer.available(t)]
        if missing:
            raise HTTPException(503, f"models not trained: {missing}; run scripts/train_model.py")
        fx = fixture_from_context(await client.context(org_id, account_id))
        x = features_from_fixture(fx)
        out: dict[str, Any] = {"account_id": account_id}
        for t in ("churn", "expansion"):
            sc = Scorer.load(t)
            r = sc.explain(x, 5)[0]
            r.update({"model": sc.card["version"], "trained_on": sc.card["trained_on"], "production_ready": sc.card["release"]["production_ready"]})  # fmt: skip
            out[t] = r
        out["view"] = combined_view(out["churn"]["probability"], out["expansion"]["probability"], out["churn"]["band"], out["expansion"]["band"])  # fmt: skip
        return out

    @app.get("/v1/orgs/{org_id}/accounts/{account_id}/scores", dependencies=[Depends(auth)])
    async def scores(org_id: str, account_id: str) -> dict[str, Any]:
        """Churn + expansion probability, band and SHAP reasons for one account."""
        return await _scores(org_id, account_id)

    @app.get("/v1/orgs/{org_id}/accounts/{account_id}/churn", dependencies=[Depends(auth)])
    async def churn(org_id: str, account_id: str) -> dict[str, Any]:
        return (await _scores(org_id, account_id))["churn"]

    @app.get("/v1/orgs/{org_id}/accounts/{account_id}/expansion", dependencies=[Depends(auth)])
    async def expansion(org_id: str, account_id: str) -> dict[str, Any]:
        return (await _scores(org_id, account_id))["expansion"]

    return app
