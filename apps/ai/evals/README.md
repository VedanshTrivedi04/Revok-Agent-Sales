# Evals — current numbers and known failure patterns

Reproduce: `uv run python -m revops_ai.evals.run --suite <baseline|t1|t2|t3|e2e> [--live]`; results are written
to `evals/results/<suite>-<tag>.json`. **All numbers below are OFFLINE** (deterministic `HeuristicLLM`
stand-in): they prove the pipeline, validators, metrics and gates work. They say nothing about the quality of
Qwen3.5-9B; those numbers need the cloud endpoint (`--live`, see `infra/cloud/README.md`).

## Offline results (30 golden accounts, 161 labeled messages, 30 adversarial injections)
| Suite | Metric | Value | Gate |
|---|---|---|---|
| baseline (no AI) | signal recall with NullSignalExtractor | 0.0 | what AI must beat |
| baseline | reference engine == expected rule hits | 30/30 | – |
| t1 | signal precision / recall | 1.00 / 1.00 | P>=0.85, R>=0.70 (live) |
| t1 | JSON validity | 1.00 | >=0.995 |
| t1 | injection resistance (flagged + quarantined) | 1.00 (10/10) | 1.00 |
| t1 | adversarial variants flagged | 1.00 (30/30) | – |
| t2 | raw citation validity | 1.00 | >=0.90 (live) |
| t2 | post-validator citation validity | 1.00 | 1.00 |
| t2 | number fidelity of shown claims | 1.00 | >=0.98 |
| t2 | fallback rate (19 flagged cases) | 0.053 (1/19) | <0.10 |
| t3 | banned phrases after validation | 0 | 0 |
| t3 | recipient correctness / mapped payload validity | 1.00 / 1.00 | 1.00 |
| e2e | rule hits equal expected after T1 -> rules | 29/30 | all |
| e2e | failed runs / backend rejections | 0 / 0 | 0 |

Why e2e is 29/30: `non_english_signal` (Spanish competitor mention). The stand-in is English-only; this is
a deliberate probe for the real model (T1 must extract it for the rule `R07` to fire).

## Churn model (SYNTHETIC data — pipeline check, not real-world accuracy)
Time-based split (train <=2024, valid 2025H1, calib 2025H2, test 2026): 12 000 renewals, 17% churn/downgrade.
| Model (test) | AUC-ROC | AUC-PR | Brier | ECE | Top-decile lift |
|---|---|---|---|---|---|
| LightGBM + isotonic | 0.797 | 0.496 | 0.119 | 0.020 | 3.24 |
| Logistic regression baseline | 0.807 | 0.518 | 0.118 | 0.025 | 3.37 |
| Rules-severity score baseline | 0.779 | 0.435 | – | – | 3.02 |

Honest reading: on this synthetic data LightGBM does **not** beat logistic regression, because the generating
process is almost linear. On real data this must be re-measured; the pipeline (`scripts/train_churn.py --csv`)
is ready. `show_probability` is true only because ECE < 0.05 on synthetic data; keep it off in the product
until retrained on real renewals (model card says so).

## Live results on Qwen3.5-9B (cloud GPU, 2026-10-11; files in `evals/results/`)
| Run | What | Result |
|---|---|---|
| `t1-live1` / `t1-b1` | extract@1.0.0 | precision 0.768, recall 0.993: precision gate failed |
| `t1-a1` | extract@1.1.0 | precision 0.993, recall 0.950: all gates pass |
| `t1-b2` | extract@1.1.1 (current default) | precision 0.890, recall 0.986, JSON 1.0, injection 1.0: all gates pass |
| `t1_i18n-b1` | non-English / HTML / long mail, 20 messages | precision 1.0, recall 1.0 |
| `t2-live1` | explain, first validator | number fidelity 0.932, post-validator 0.952: failed |
| `t2-b1` | explain, fixed validator | raw citation 1.0, post-validator 1.0, number fidelity 1.0, fallback 0: all gates pass |
| `t3-live1` | drafts | banned phrases 0, recipients 1.0, payloads 1.0: all gates pass |
| `e2e-live1` | full graph, 30 cases, before the T1 prompt fix | 29/30 rule hits (`very_long_email`); not re-run since |

The result files do not record the prompt version; the T1 versions above are matched by file timestamps
(1.1.0 written 12:19, 1.1.1 written 12:35). Record the version in the result file on the next live run.

Latency on that endpoint (T4, GGUF): T1 p95 about 6 s, T2 p50 about 18-22 s, T3 p95 about 30 s. The e2e
suite and the integrated stack have not been re-run on the real model after the fixes.

## Known failure patterns / watch-list for the live run
1. Qwen3.5 thinks by default; the client forces `enable_thinking=false`. If latency or `<think>` text appears,
   check the vLLM version honours `chat_template_kwargs`.
2. Structured-output flag differs by vLLM version: try `LLM_STRUCTURED_MODE=response_format|structured_outputs|guided_json`
   (`scripts/smoke_structured.py` reports validity per mode).
3. Single-rule findings can yield fewer than 2 valid claims -> template fallback (needs_review). If live
   fallback >10%, raise claim variety in the prompt (cite renewal + rule) before changing the 2-claim rule.
4. Non-English emails and HTML-heavy mail: T1 recall unmeasured on the real model.
5. Number rounding: validator accepts 38 for 38.5 (floor/half-up) but not 38.4; adjust only with an ADR.

## Integration with the backend
The contract gaps that used to be listed here are closed on both sides; see
`docs/ai-backend-requests.md` (how a run is triggered, what the context contains, how AI drafts upgrade
template cards, what is still open). `tests/unit/test_a7_external.py` runs the service against a fake
backend that validates every request with the backend's OpenAPI snapshot
(`revops-agent/apps/api/tests/snapshots/openapi.internal.json`) and serves backend-style evidence labels.

## Phase A8 (hardening) - what was measured offline
- Pipeline overhead (no LLM): 500 accounts through the full graph in 5.7 s at concurrency 16 (87 accounts/s),
  run p95 0.26 s. So the nightly window is decided almost entirely by Qwen3.5-9B throughput; measure with
  `scripts/load_nightly.py --accounts 500 --concurrency 16 --live` (target: < 30 min).
- Promotion rules (`scripts/promote.py`, `evals/promotion.py`): all gates pass AND no gated metric may regress
  by more than 2 points vs the baseline (use for quantization, model and prompt changes). Canary decision
  (`canary_decision`): needs >= 30 cards and >= 20 findings; rollback if approval drops > 5 points or
  "not useful" rises > 5 points.
- Security: `pip-audit` reported no known vulnerabilities; `scripts/egress_check.py` passes; tests assert no
  customer content in logs/traces and no secrets in the repo.
- NOT done (needs the real model / time): full eval on Qwen3.5-9B, quantization comparison, real canary week,
  7-day soak on staging, human review of 10 outputs.
