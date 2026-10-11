# RevOps Agent — AI/ML service (`apps/ai`)

Everything AI/ML lives here (separate uv project, `revops_ai` package). It does **not** import or modify
`apps/api` (backend) or `apps/web`; it talks to the backend only through `/internal/v1` and the ports
described in `docs/ai-implementation-plan.md`.

## What is built
| Area | Where | Status |
|---|---|---|
| LLM client (OpenAI-compatible, vLLM structured output, thinking off, retries, no tools ever) | `revops_ai/llm/client.py` | done, tested |
| Prompts (versioned) `extract/explain/draft@1.0.0` | `revops_ai/prompts/*.md`, `llm/prompts.py` | done |
| T1 signal extraction + injection pre-filter + exact-quote validator | `tasks/extract.py`, `validation/injection.py`, `quotes.py` | done |
| Evidence: reference engine (rules R01-R11/X01-X05, detectors, numbering), render, conformance | `evidence/` | done |
| T2 explanation + citation/number/entity validator + retry + template fallback | `tasks/explain.py`, `validation/citations.py`, `numbers.py`, `fallback/` | done |
| T3 drafts + post-validation + mapping to backend payloads | `tasks/draft.py`, `validation/actions.py`, `adapters/backend_contract.py` | done |
| LangGraph run (checkpointed, interrupt for approval) | `graph/` | done; Postgres restart test passes on a real container |
| Tracing/masking/alerts/versions/canary | `observability/` | done (Langfuse sink written, **not run against a Langfuse server**) |
| External mode: `/internal/v1` client, worker, service API | `adapters/internal_client.py`, `external.py`, `worker.py`, `service.py` | done against a reference fake validated with the backend's OpenAPI snapshot |
| Churn model: synthetic dataset + LightGBM + isotonic calibration + SHAP reasons | `ml/` | trained on **SYNTHETIC** data |
| Eval runner and suites `baseline,t1,t2,t3,e2e` | `evals/` | done; numbers below are offline plumbing numbers |

## Quick start
```bash
cd apps/ai
uv sync
uv run python scripts/gen_golden.py        # 30 golden accounts + 161 labeled messages (deterministic)
uv run python scripts/train_churn.py       # synthetic renewals dataset + model -> models/churn
uv run pytest -q                           # offline suite (no GPU needed)
uv run python scripts/demo.py              # whole loop, offline stand-in model
```

## Running with the product (backend + frontend)
```bash
# 1. model endpoint: see infra/cloud/README.md, then in apps/ai/.env set LLM_BASE_URL / LLM_API_KEY
#    and INTERNAL_API_URL=http://localhost:8000/internal, INTERNAL_API_KEY=<same as the backend>
uv run uvicorn revops_ai.main:app --port 8100          # GET /health?deep=true shows llm_ok
# 2. backend (revops-agent/apps/api/.env): AI_MODE=external  AI_SERVICE_URL=http://localhost:8100
#    restart the API and the Celery worker + beat
```
Then "Run agent now" on an account: the finding appears at once with the rule-based summary and template
cards, and a few seconds later the page refreshes with the AI explanation and the redrafted email card.
With the model endpoint down nothing breaks: the rule-based result stays. Docker: `--profile ai` in
`revops-agent/infra/docker-compose*.yml`. Details: `docs/ai-backend-requests.md`.

## Local demo UI (browser)
```bash
uv run python scripts/demo_ui.py          # then open http://127.0.0.1:8765
```
Pick one of the 30 synthetic accounts and see the 6 steps: data, signals + rules, cited explanation, proposed
actions, approve/reject, and (simulated) execution. Offline stand-in model by default; tick "use live Qwen
model" for the real endpoint. It is a viewer, not the product frontend (`apps/web` is untouched).

## Using the real Qwen3.5-9B
The laptop cannot run it (7.7 GB RAM, no NVIDIA GPU), so it is served from a cloud GPU:
see `infra/cloud/README.md` (script `serve_qwen.sh` or notebook `qwen35_vllm.ipynb`; downloads the real
~18 GB weights). Then:
```bash
cp .env.example .env     # set LLM_BASE_URL=https://<tunnel>/v1 and LLM_API_KEY
uv run python scripts/smoke_structured.py --n 50           # JSON validity + latency per schema
uv run pytest -m live tests/live -q                        # gates on the real model
uv run python -m revops_ai.evals.run --suite t1 --live     # also t2, t3, e2e
uv run python scripts/demo.py --live --all
```
Verified locally from the model repo: the chat template exposes `enable_thinking` (default thinking is ON,
so the client sends `enable_thinking=false`), and the architecture is `Qwen3_5ForConditionalGeneration`
(config files are in `models/qwen3.5-9b-meta/`).

## Hard rules enforced by tests
No tools/function-calling in LLM requests, no backend/provider imports, no external AI SDKs, injection
sentences never reach the model, every shown claim has valid evidence and supported numbers, recipients only
from the contact allowlist, banned pricing language never survives, payloads validate against mirrored
backend models (checked against backend source by AST) and requests against the backend OpenAPI snapshot.

## Known limits (be honest in demos)
- Live numbers on Qwen3.5-9B exist for T1, T2 and T3 (`evals/README.md`); the e2e suite and the integrated
  stack have not been re-run on the real model after the last fixes.
- The churn/expansion model is trained on synthetic data and is not shown in the product.
- The model endpoint used so far is a rotating tunnel on a rented GPU; it is not a deployment.
