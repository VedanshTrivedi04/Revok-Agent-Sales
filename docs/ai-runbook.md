# AI runbook (apps/ai)

Audience: whoever is on call for the AI service. Commands run from `apps/ai`. Nothing here touches the
backend; the backend keeps working in `template` mode whenever the AI service is down.

## 0. Quick facts
- Model: `Qwen/Qwen3.5-9B` on vLLM (cloud GPU), OpenAI-compatible at `LLM_BASE_URL`. Thinking is OFF (`LLM_ENABLE_THINKING=false`).
- Service: `revops_ai.service` (FastAPI, header `X-AI-Key`), runs LangGraph with Postgres checkpoints.
- Safe degradation: every failure ends in the template explanation (`needs_review`), never in uncited text.
- Alerts (observability/tracing.py `check_alerts`): fallback rate > 20% in 1 h; LLM p95 > 20 s.

## 1. Model down (connection errors, 5xx, timeouts)
Symptoms: runs finish with `fallback=true` and `model=template`; `llm_calls` errors in the trace; alert `fallback_rate_over_20pct`.
1. `curl -H "Authorization: Bearer $LLM_API_KEY" $LLM_BASE_URL/models` – if it fails the GPU host/tunnel is down.
2. Restart vLLM (`bash infra/cloud/serve_qwen.sh` or re-run the notebook cells); tunnels change URL: update `LLM_BASE_URL`.
3. Nothing is lost: findings already have the template explanation. Re-run affected accounts (`POST /v1/runs`, trigger `retry`).
4. If the outage is long, set the backend to `AI_MODE=template` (backend setting) so it stops calling the service.

## 2. High fallback rate (> 10% normal, > 20% alert)
1. Look at `evals/results/e2e-*.json` `per_case` and traces: is the cause `conformance:*` (bad evidence from the backend), `fewer than 2 valid claims`, or invalid JSON?
2. Conformance violations -> the backend evidence builder changed; run `evidence/render.py::conformance` on a sample and tell Rajwardhan.
3. Few valid claims -> run `uv run python -m revops_ai.evals.run --suite t2 --live`; compare with the last good result using `scripts/promote.py --baseline-tag <good> --candidate-tag <now>`.
4. If a recent prompt/model change caused it, follow section 4.

## 3. JSON failure storm (`output was not valid JSON`)
1. `uv run python scripts/smoke_structured.py --n 20` – validity per schema.
2. Wrong structured-output flag after a vLLM upgrade: try `LLM_STRUCTURED_MODE=response_format | structured_outputs | guided_json`.
3. `<think>` blocks in output: confirm `chat_template_kwargs.enable_thinking=false` is honoured by the vLLM version.
4. GPU memory pressure can truncate output: lower `--max-model-len` / concurrency (section 5).

## 4. Rollback a prompt or model
1. Prompts are files `revops_ai/prompts/<task>.<semver>.md`; old versions stay loadable. The active version is the highest semver.
2. Fast rollback: delete (or rename out of the pattern) the newest file, redeploy; or pin per org with `select_prompts(org, canary_pct=0)`.
3. Canary: `select_prompts(org, canary_pct=10, candidate={"explain": "1.1.0"})`; after one week run `canary_decision()` (evals/promotion.py) with approval and "not useful" rates; it returns promote / rollback / extend.
4. Never promote on speed alone: `scripts/promote.py --baseline-tag <old> --candidate-tag <new>` must print `PROMOTE`.

## 5. GPU out of memory / slow
- Lower `--max-model-len` (16384 -> 8192; prompts are <= ~6k tokens) and `--gpu-memory-utilization` (0.90 -> 0.85).
- Lower worker concurrency (`EXTRACT_CONCURRENCY` in graph/graph.py, `--concurrency` in `scripts/load_nightly.py`).
- Use FP8/AWQ only after `scripts/promote.py --baseline-tag bf16 --candidate-tag awq` passes (quantization can change citation validity).
- Nightly capacity check: `uv run python scripts/load_nightly.py --accounts 500 --concurrency 16 --live`.

## 6. Swap or upgrade the model (skill S11)
1. Deploy the new model on a second port; set a temporary `.env` pointing at it.
2. Run all suites with a tag: `for s in t1 t2 t3 e2e; do uv run python -m revops_ai.evals.run --suite $s --live --tag <new>; done`.
3. `uv run python scripts/promote.py --baseline-tag <current> --candidate-tag <new>` – gates + no regression > 2 points.
4. Human-review 10 random outputs (`evals/reviews/TEMPLATE.md`), then canary (section 4), then update ADR-005 in `docs/thinking.md`.

## 7. Injection incidents
- A message flagged `suspicious_instruction` is quarantined: the sentence is redacted before the model sees it, evidence shows only the fixed label.
- If something slipped through: add the text to `synth/adversarial.py` + `validation/injection.py` patterns, add a test, run `uv run pytest tests/unit/test_a2_extract.py`.
- Check `scripts/egress_check.py` and the trace/log leakage test (`tests/unit/test_a8_hardening.py`) stay green.
- Rotate keys if a leak is suspected: `LLM_API_KEY` (vLLM `--api-key`) and `INTERNAL_API_KEY` (backend + `.env` of the AI service).

## 8. Stuck or duplicated runs
- A run waiting for approval survives restarts (Postgres checkpoint). Resume with `POST /v1/runs/{id}/resume`.
- A second run for the same account while one is active returns 409 by design.
- Backend 5xx on status/proposals: calls retry 3x with backoff, then the run is recorded as `failed`; re-trigger with `trigger=retry`.

## 9. Dependency and secret hygiene (before each release)
```bash
uv export --no-hashes -o req.txt && uvx pip-audit -r req.txt --no-deps --disable-pip
uv run python scripts/egress_check.py
uv run pytest -q tests/unit/test_a8_hardening.py
```
