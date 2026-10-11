# AI <-> Backend integration: contract and status

Written for: Vedansh (control plane, `/internal/v1`), Rajwardhan (rules, context, evidence) and the AI
engineer. This replaces the earlier list of open requests: the gaps below are now closed in code on both
sides (`revops-agent/apps/api` and `apps/ai`). Section 4 lists what is still open.

## 1. How the two services work together (AI_MODE=external)

1. A run (`run.account`, nightly or "Run agent now") builds context, rules, evidence and the finding
   exactly as in template mode. The finding is committed with the **template explanation and template
   cards**. This baseline is always there.
2. After the commit the worker enqueues `run.ai_enhance` for each open finding that carries the template
   explanation. It calls the AI service: `POST {AI_SERVICE_URL}/v1/runs {org_id, account_id, finding_id,
   run_id, trigger}` (header `X-AI-Key` = `INTERNAL_API_KEY`). Only ids travel.
3. The AI service reads `GET /internal/v1/orgs/{org}/accounts/{id}/context?finding_id=`, writes an
   explanation (`POST .../findings/{id}/explanation`) and proposals (`POST .../findings/{id}/proposals`),
   then reports to `POST .../runs/{run_id}/status`. The backend validates every write again.
4. The backend publishes `finding.updated` / `card.updated` on SSE, so open pages refresh.

If the AI service or the model is down, slow or wrong: the Celery task retries with backoff, the AI's
own validators fall back, and the template result simply stays. A failed AI phase is recorded under
`agent_runs.stats.ai`; it never turns a finished run into `failed`.

Signals (T1): a beat task (`run.ai_extract_dispatch`, every 10 min) asks the AI service to read pending
events; a manual run first waits (max `AI_EXTRACT_WAIT_S`) for the events of that account.

ML scores: every run also enqueues `run.ai_scores`, which reads
`GET {AI_SERVICE_URL}/v1/orgs/{org}/accounts/{id}/scores` and stores the result in `accounts.ml_scores`
(migration `0007`). `GET /today`, `GET /accounts` and `GET /accounts/{id}` return it as `ml_scores`
(`churn` / `expansion`: probability, band, top reasons). SSE `account.updated` refreshes open pages. An
account that has not been scored yet has `ml_scores = null` and the UI shows a dash.

## 2. Contract changes made (all additive)

| # | Earlier gap | Now |
|---|---|---|
| 1 | `ContextOut` had no finding id; evidence of all findings of an account was mixed (duplicate `E1`) | `?finding_id=`; `ContextOut.finding` (id, type, severity, rule_keys, unknowns, contradictions); evidence of that finding only, in numeric key order |
| 2 | Nobody triggered the AI | Backend pushes after commit (`run.ai_enhance`); AI queues runs per account |
| 3 | No unknowns / contradictions | In `ContextOut.finding`; the run now passes detected contradictions to the explainer with their evidence key (they were dropped before) |
| 4 | `ProposalIn` had no `flags` | `flags: list[str]`; known flags become a reviewer note on the card, all are logged |
| 5 | No tier in the response | `ProposalsSavedOut.cards[] = {card_id, type, tier, status, action}` |
| 6 | No `no_finding` status | Added; plus `model` and `prompt_versions` on `RunStatusIn` |
| 7 | `rule_hits` was always empty (rule hits were never persisted) | Context reads hits from the finding's rule-metric evidence (`human_text`, `evidence_key`); runs also persist `rule_hits` rows for the finding page |
| 8 | Account had no provider ids | `account.crm_id`, `account.owner {name, crm_owner_id, slack_user_id}`, `org {name, domains, health_property, health_values, next_step_property}`, `now` |
| 9 | Pending events included unmatched/empty events; an event with no signals was served forever | Only text events matched to an account; every read event is marked; re-extraction replaces signals; `?account_id=`; `org_name`, `account_name` |
| 10 | Quote had to match byte for byte | Whitespace-insensitive substring (a quote may span a line break) |

Card rule: a valid AI proposal **redrafts the pending card of the same type** for the finding when no
person has edited it (`card.redrafted` in the decision log); otherwise it creates a card, or is reported
as `duplicate`. AI proposals pass the same validator as a user edit (`validate_card_payload`).

## 3. Bugs fixed on the way

- `run.account` did not accept the `(session, org_id, ...)` call made by `tenant_task`; every run in a real
  worker failed. Covered by `tests/test_ai_integration.py`.
- `ExternalExplainer` wrote a placeholder summary with no claims. Removed: both modes use the template
  ports in-process.
- `GET /admin/llm/health` returned fixed values. It now reports the real mode, model and probe latency.
- The staging compose file had no Celery worker or beat service. Added (`worker`, `beat`, optional `ai`).

## 4. Still open

1. **Evidence quality (Rajwardhan):** items like `Supporting usage record / Reference ID: <uuid>` carry no
   readable fact. The AI ignores their detail; real labels (event title and date, usage period) would
   improve both the finding page and the explanations.
2. **Stable model endpoint:** a rotating tunnel is not a deployment. Staging needs a fixed GPU host.
3. **Approval feedback to the AI run:** runs end after reporting (`AI_WAIT_FOR_APPROVAL=false`). The
   resume endpoint exists; the backend does not call it.
4. **Account scores (churn/expansion model)** are shown in the product but the model is trained on
   synthetic data (`MlScores.synthetic = true`, stated on the account page). Retrain on real renewals
   (`apps/ai/scripts/train_model.py --csv`) before treating the numbers as a forecast.
5. **Live end-to-end eval** against the integrated stack has not been run (needs the model endpoint).
