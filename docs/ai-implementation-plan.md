# ai-implementation-plan.md — AI/ML Phase-wise Implementation Plan

> Scope: **only the AI/ML part** (model serving, LLM client, T1/T2/T3 tasks, evidence handling on the AI side, validators, agent graph, evals, observability, Phase 2/3 ML).
> Nothing in `apps/api` (backend) or `apps/web` (frontend) is changed by this plan. Where the AI work needs something from the backend, it is listed as a **request** to Vedansh / Rajwardhan, never done by us.
> Sources: `aiengineerhandover.md` (task spec), `agent.md` §3 (hard rules), `algorithm.md`, `backend-plan.md` §2, `task.md` (AI-xx ids), and the code state of `apps/api` on 2026-10-11 (ports + `/internal/v1` stubs only).
> Written for: the AI/ML engineer (owner of this plan). Tasks keep the ids `AI-xx` from `task.md`; new ids are `AI-A<phase>-<nn>`.

---

## 0. Starting point and key decisions

### 0.1 What exists vs what we build
| Exists (backend, do not touch) | We build (AI side) |
|---|---|
| `app/ports/` protocols (`SignalExtractor`, `Explainer`, `ActionPlanner`), `AI_MODE`, `registry.override()` | Implementations of those protocols |
| `/internal/v1` 7 routes (501 until backend V6-02), `X-Internal-Key` | HTTP client for them + worker that drives a run |
| Tables `signals`, `finding_evidence`, `agent_runs`, `findings.model/prompt_version` | Prompt/model version values written through the API |
| Demo/seed dataset (Acme, Globex, Initech, Umbrella, Hooli, Soylent) | Golden fixtures derived from it |
| A test forbidding AI SDK imports inside `apps/api/app` | **A separate package** so that test stays green |

### 0.2 Decisions (assumptions to confirm in week 1; each is cheap to change)
| # | Decision | Why |
|---|---|---|
| D1 | All AI code lives in a **new, separate uv project `apps/ai/`** (package `revops_ai`), not in `apps/api/app/agent|llm`. This deviates from the folder names in `aiengineerhandover.md` / `backenddeveloper.md`. | `test_no_ai_sdk_is_imported_by_the_backend` forbids openai/langgraph/etc. in `apps/api/app`; the instruction "don't touch backend" is respected; the backend's own design (ports + `/internal/v1`, `AI_MODE=external`) is built for exactly this. |
| D2 | Two integration modes, same core code: **(a) in-process adapter** (implements the ports, used in tests/early dev through `registry.override()`) and **(b) external worker** that talks only to `/internal/v1` (production target, `AI_MODE=external`). | Lets us work before backend V6-02 ships, without a refactor later. |
| D3 | The AI package defines its **own internal Pydantic models** (handover schemas) and a thin **`adapters/backend_contract.py`** that converts to/from the backend DTOs. All mismatches below are solved in that one file. | Backend contracts are shared boundary files; changing them needs both backend devs. We absorb differences first, then propose changes only if needed. |
| D4 | LangGraph is used **only after** T1/T2/T3 work as plain async functions. Nodes are thin wrappers over those functions. | ADR-006 note: keep business logic in plain functions. |
| D5 | All development data is synthetic (`*.example.com`). No customer data to any external API. | agent.md rules 10, 11. |
| D6 | LLM never receives tools. No function-calling code is written anywhere. | agent.md rule 1. |

### 0.3 Contract mismatches and how the AI side absorbs them
| # | Mismatch | Handover | Backend today | Resolution in `adapters/backend_contract.py` |
|---|---|---|---|---|
| M1 | Draft proposals | `to_contact_ids`, `due_in_days`, logical `field_key` | `EmailDraftPayload(to: emails)`, `CrmTaskPayload(due_date, owner_crm_id, associate)`, `CrmFieldChange(field=real property, before, after)` | Deterministic mapper (code, not LLM): ids→emails from contacts list, `due_date=today+n`, `field_key`→property via field mapping, `before` from account context |
| M2 | Confidence label | `strong/moderate/weak` | `high/medium/low` | Map strong→high, moderate→medium, weak→low; keep the original in `run stats` |
| M3 | Signal `value` | `str | None` | `dict` | `{"value": "<str>"}` or `{"competitor": ...}` by kind (`competitor_mention`→`competitor`, `champion_leaving`→`person`, `feature_request`→`feature`, else `value`) |
| M4 | Context shape | one evidence list + rule hits + `missing_data` | `ContextOut.missing_data` vs port `ExplainCtx.unknowns/contradictions` | Our `RunContext` model is built from `ContextOut`; detectors' unknowns/contradictions arrive as evidence/`missing_data` |
| M5 | Evidence `ref_id` | present in handover `Evidence` | absent from `EvidenceOut` | Not needed by LLM; keep `key/kind/label/detail/source/occurred_at` only. Ask backend for `ref_id` later only if replay needs it |
| M6 | Queue name | `agent` | `run` | Irrelevant to external worker; use `run` if we ever enqueue |
| M7 | Evidence builder owner | "AI+BE" (handover) vs Rajwardhan R3-04 deterministic builder | not built | AI builds a **reference builder** for evals (A3) and a **conformance test** that the backend's output obeys `algorithm.md` §8; production uses the backend's list (it already numbers E1..En) |

### 0.4 Dependencies on backend (requests, not work for us)
| Need | Owner | Needed by | Workaround until then |
|---|---|---|---|
| `rules` engine, context builder, evidence builder (R3-01..05) | Rajwardhan, backend Phase 3 | A4 real data | Reference rules/evidence in fixtures (`expected.json`) |
| `/internal/v1` real implementation (V6-02) + `docs/ai-integration.md` | Vedansh, Phase 6 | A7 | Local fake server in `apps/ai/tests/fake_backend.py` that mirrors `schemas/internal.py` |
| `cards.create_from_proposals()` + policy | Vedansh, Phase 2/3 | A5/A7 | Our validators run first; backend re-validates anyway |
| Langfuse service in compose | Vedansh/OPS | A6 | Local Langfuse via our own compose file under `apps/ai/` |
| GPU host | OPS | A0 | Ollama locally; rented GPU for AI-01 |

---

## 1. Target layout (`apps/ai/`)

```
apps/ai/
  pyproject.toml            # uv; deps: openai, pydantic, jinja2, httpx, tenacity, langgraph, langgraph-checkpoint-postgres, langfuse, structlog, pytest, ruff, mypy
  revops_ai/
    config.py               # LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, INTERNAL_API_URL, INTERNAL_API_KEY, LANGFUSE_*
    llm/        client.py (call_json, retries, usage), schemas.py (ExtractOutput, ExplainOutput, DraftOutput)
    prompts/    extract.1.0.0.md  explain.1.0.0.md  draft.1.0.0.md   # Jinja2, versioned
    tasks/      extract.py  explain.py  draft.py                     # plain async functions (T1/T2/T3)
    validation/ quotes.py  citations.py  numbers.py  entities.py  banned.py  actions.py  injection.py
    evidence/   reference_builder.py  conformance.py                 # algorithm.md §8
    fallback/   templates.py                                          # no-LLM explanation
    graph/      state.py  nodes.py  graph.py  checkpoint.py
    adapters/   backend_contract.py  ports_impl.py  internal_client.py  worker.py
    observability/ tracing.py  masking.py  metrics.py
    evals/      run.py  metrics.py  judge.py  report.py
  tests/        unit/  golden/cases/<nn>_<name>/  recorded/  fake_backend.py
  evals/        results/  reviews/  README.md
  infra/        docker-compose.ai.yml (vLLM or ollama, langfuse, postgres for checkpoints in dev)
```
CI: new workflow job `ai` (ruff, mypy, pytest, eval smoke on recorded responses) added by us as a separate file (`.github/workflows/ai.yml`), not by editing the backend job.

---

## 2. Timeline overview

| Phase | Weeks | Goal | Key task ids | Exit gate |
|---|---|---|---|---|
| **A0 Foundation & model** | 1–2 | Model chosen and served, structured output proven, project skeleton, LLM client | AI-01, AI-10 | 50/50 schema-valid calls; traces visible |
| **A1 Golden data & eval harness** | 2–4 | Test-first base: fixtures + metrics before prompts | AI-02, part of AI-17 | `pytest -m golden` runs; baseline (no-LLM) numbers recorded |
| **A2 T1 signal extraction + injection** | 4–6 | Signals with exact quotes, quarantine of injections | AI-11, AI-18 (part) | P ≥ 0.85, R ≥ 0.70, injection 100% |
| **A3 Evidence layer** | 5–7 | Conformant, deterministic evidence for prompts | AI-12 | Evidence conformance tests green on all golden cases |
| **A4 T2 explain + validator + fallback** | 6–9 | Cited explanations, 100% valid after validation | AI-13, AI-14 | raw citation ≥ 90%, number fidelity ≥ 98%, fallback < 10% |
| **A5 T3 drafts + action validation** | 8–11 | Safe typed proposals, mapped to backend payloads | AI-15, AI-18 (rest) | 0 banned phrases, 100% allowed recipients |
| **A6 Orchestration, observability, versioning** | 10–13 | Graph with checkpoints, Langfuse, versions, CI eval smoke | AI-16, AI-17, AI-20, AI-21 | run survives worker restart; alerts fire in staging |
| **A7 Backend integration (external mode)** | 13–16 | Run through `/internal/v1` end to end | (AI side of V6-02) | Acme loop on staging; `AI_MODE=external` works |
| **A8 Hardening, canary, handover** | 16–18 | Promote prompts/model, runbooks, docs | – | Full eval gates pass; 7-day soak with no manual fix |
| **A9 Phase 2: learning from humans** | pilot | Draft preferences, rejection analysis, threshold suggestions | P2-02, P2-10 | Visible, reversible suggestions only |
| **A10 Phase 3: churn model** | after data | Calibrated churn probability | P3-02 | Calibration error < 0.05 on holdout |

Phases A1–A5 can run mostly against fixtures and recorded/fake backend, so they do **not** wait for backend phases. Real-data checks wait for Rajwardhan's Phase 3 and Vedansh's Phase 6.

---

## Phase A0 — Foundation & model (weeks 1–2)

**Goal:** remove the biggest unknowns (which model, can it emit schema-valid JSON, how fast) before writing prompts.

| ID | Task | Detail | Done when |
|---|---|---|---|
| A0-01 (AI-01) | Confirm model version | Ask the founder for the source of "Qwen 3.9 9B"; otherwise take Qwen3.5-9B (fallback Qwen3.8-27B). Record the decision as an ADR in `docs/thinking.md` (new ADR, do not edit ADR-005). Check license and context length on the model card. | ADR written |
| A0-02 | Serving | Rent/borrow one 24 GB GPU. `vllm serve` with `--max-model-len 16384 --enable-prefix-caching --api-key`. Pin the vLLM version; read that version's docs for structured outputs (`guided_json` vs `structured_outputs`/`response_format`). Local fallback: Ollama with same model. | `curl /v1/models` works; version pinned in `infra/` |
| A0-03 | Structured-output smoke | Script `scripts/smoke_structured.py`: 50 calls each for `ExtractOutput`, `ExplainOutput`, `DraftOutput` with toy inputs; measure JSON validity, p50/p95 latency, tokens/s; thinking mode on/off. | 50/50 valid for each schema; numbers in `evals/README.md` |
| A0-04 | Skeleton | `apps/ai` uv project, ruff + mypy strict, pytest, pre-commit, `config.py` (env only), `.env.example` in `apps/ai`, `ai.yml` CI. | CI green on empty project |
| A0-05 (AI-10) | LLM client | `llm/client.py`: `call_json(task, messages, schema, temperature, max_tokens)`; timeout 60 s; tenacity retry on 429/5xx/timeouts; parse error → raise `LLMOutputError` (caller decides retry); returns parsed model + usage (tokens, latency); `request_id` logging **without** message content. A `FakeLLM` with recorded responses for tests; `--record` mode saves responses to `tests/recorded/`. | Unit tests with `respx`; no content in logs (log-capture test) |
| A0-06 | Tracing stub | `observability/tracing.py` wrapper around Langfuse `observe` with a no-op fallback; masking function (emails/phones) applied before send. | Trace appears in local Langfuse for a smoke call |
| A0-07 | Contract mirror | Copy backend DTO shapes into `adapters/backend_contract.py` as our own models + a **contract test** that loads `apps/api/tests/snapshots/openapi.internal.json` (read-only) and fails if the shapes drift. | Test green; drift is detected, not silently absorbed |
| A0-08 | Hard-rule tests | Tests that grep our package for: any tool/function-calling params in LLM calls, any write call to providers, any import of backend `executor`. | Green |

**Risks:** model version unclear → decide with fallback 27B in parallel; guided decoding syntax differs per vLLM version → wrap in one function `structured_kwargs()`.

---

## Phase A1 — Golden dataset and eval harness (weeks 2–4)

**Goal:** test-first. Fixtures and metrics exist before any prompt, so every later change is measured (superpower.md §3).

| ID | Task | Detail |
|---|---|---|
| A1-01 (AI-02) | Fixture format | `tests/golden/cases/<nn>_<name>/{account.json, events.jsonl, usage.json, contacts.json, expected.json, README.md}`; fixed `now` per case; synthetic names/domains only. `expected.json` fields per handover §8.1 (`rule_hits`, `finding_type`, `severity`, `must_cite`, `forbidden`, `signals_expected`, `actions_expected`, plus `contradictions_expected`, `unknowns_expected`). |
| A1-02 | First 12 cases from the seed | Acme (clear risk, contradiction Green vs −38%), Globex (expansion), Initech (competitor mention), Umbrella (healthy, no finding), Hooli (injection), Soylent (no usage). Reuse `app/mocks/data.py` content as **read-only reference**; copy values into fixtures (no import of backend code). |
| A1-03 | Expand to 30 | Add: noisy internal emails, positive emails + usage drop, champion left, renewal far away, multi-domain account, free-mail contact, seat underuse, single-threaded, no next step, pricing concern, negative sentiment escalation, upgrade intent, missing renewal date, stale integration, long email thread, non-English snippet, HTML-polluted text, very long email (truncation), two injections in one thread, empty body. Coordinate with Rajwardhan so `rule_hits` expectations match `algorithm.md` §4 (he owns R3-09 golden for rules; share the same account fixtures to avoid two copies). |
| A1-04 | Message-level labeled set for T1 | 100+ short synthetic messages (inbound/outbound) with labeled signals and exact quotes (≥ 8 per signal kind incl. negatives where nothing should fire). |
| A1-05 | Eval runner skeleton (AI-17 part 1) | `python -m revops_ai.evals.run --suite smoke|full --model ... --prompts ...`; deterministic seeds; outputs JSON `{metrics, per_case, versions}`; compares against previous result file and prints deltas. |
| A1-06 | Metric implementations | JSON validity, raw/post citation validity, number fidelity, unsupported-claim rate (judge hook), fallback rate, signal P/R/F1 per kind, injection resistance, banned-phrase count, recipient correctness, latency p50/p95. Unit-tested on hand-made outputs. |
| A1-07 | No-LLM baseline | Run the harness with the **fallback template** and `NullExtractor` to record baseline numbers; this is what "AI adds value" is compared against. |
| A1-08 | Review protocol | `evals/reviews/TEMPLATE.md` for human review of 10 random cases per eval. |

**Exit gate:** `pytest -m golden` passes (fixture schema + metric code), baseline results committed, fixtures reviewed by Rajwardhan for rule expectations.

---

## Phase A2 — T1 signal extraction + injection handling (weeks 4–6)

**Goal:** turn email/note text into validated signals; never act on injected instructions. Also unblocks rules R06/R07/R11/X03.

| ID | Task | Detail |
|---|---|---|
| A2-01 | Prompt `extract@1.0.0` | `prompts/extract.1.0.0.md` exactly as handover §7.1; Jinja2 render with truncation to 3000 chars; temperature 0.0, max_tokens 600. Skip outbound mail except `new_stakeholder`/`renewal_intent` (config flag, measured in eval). |
| A2-02 | Schema | `ExtractOutput` with `max_length` limits; `value` as `str` (M3 mapping to dict done in adapter). |
| A2-03 | Injection pre-filter | `validation/injection.py`: regexes (`ignore (all|previous) instructions`, `system:`, `you are now`, `mark .* closed`, etc.), plus Unicode/whitespace normalization and homoglyph folding; flagged events produce a `suspicious_instruction` signal even if the model misses it and are marked **quarantined** (label only, text excluded from T2/T3 evidence). |
| A2-04 | Quote validator | `validation/quotes.py`: whitespace-normalized exact-substring check; drop signal if absent; truncate quote to 300; confidence clamp; max 6 signals; dedupe same kind+quote. |
| A2-05 | Task function | `tasks/extract.py::extract_signals(event, account_ctx) -> list[Signal]`; one retry at same temperature on parse failure; on second failure return `[]` and mark `extraction_failed` (never raises into the graph). Concurrency limit 4, max 20 events/run. |
| A2-06 | Port adapter | `adapters/ports_impl.py::LLMSignalExtractor` implements `SignalExtractor` (returns backend `SignalIn` with `model`, `prompt_version`). |
| A2-07 | Tuning loop | Run eval → inspect false positives/negatives → adjust prompt wording (patch/minor version bump each time) → re-run. Try thinking on/off; try 9B vs 27B if recall is low. Record every run in `evals/results/`. |
| A2-08 | Adversarial set | 30 injection variants (direct, hidden in quoted reply, in signature, in HTML comment, multilingual, "assistant:" role spoof, tool-call lookalike JSON, instructions to change recipients/amounts). |

**Gate:** precision ≥ 0.85, recall ≥ 0.70, JSON validity ≥ 99.5%, **injection resistance 100%** (flagged and no downstream influence), p95 latency recorded.
**Failure plan:** if recall < 0.70 after prompt iterations → 27B model or two-pass (candidates then verification) within budget; document in an ADR.

---

## Phase A3 — Evidence layer (weeks 5–7, parallel with A2)

**Goal:** make sure the model is only ever given correct, numbered, short evidence, and that we can check the backend's builder.

| ID | Task | Detail |
|---|---|---|
| A3-01 (AI-12) | Reference evidence builder | `evidence/reference_builder.py` implementing `algorithm.md` §8 on fixture data: order (account facts → rule_metric per hit → hit-referenced events → signals ≤4 → contradictions ≤3 → deals ≤2), dedupe, cap 15, E1..En, labels with exact numbers/ISO dates. Pure functions, deterministic. Used by evals and as the oracle for conformance. |
| A3-02 | Conformance suite | `evidence/conformance.py`: given any evidence list (from fixtures now, from `/internal/.../context` later) assert: ≤15 items, keys sequential, labels contain the numbers present in `rule_hits.metrics`, no raw HTML, snippet ≤300 chars, quarantined events appear only as the standard label, ISO dates. Failing conformance in production → run falls back (A4) rather than prompting with bad evidence. |
| A3-03 | Prompt formatting | Renderer for `E3 | gcal | 2026-09-19 | label — detail`; strict escaping so evidence text cannot close delimiters or fake an `E` line; snippet clipping. |
| A3-04 | Number/date normalizer | Shared by validator: normalizes `38%`, `38.5%`, `−38%`, `-38`, `$84,000`, `84k`, `2026-11-22`, `Nov 22`, `22 Nov 2026`; unit-tested heavily (this is the validator's backbone). |
| A3-05 | Coordination note to backend | Short written list of what the AI side needs from R3-04 (label format, `rule_metric` fields, contradiction/unknown as evidence items, `missing_data`); agreed in the weekly sync. |

**Gate:** conformance tests green on all 30 golden cases using the reference builder; normalizer property tests pass.

---

## Phase A4 — T2 explanation, validator, fallback (weeks 6–9)

**Goal:** every sentence shown to users is cited and verified; failure degrades safely.

| ID | Task | Detail |
|---|---|---|
| A4-01 (AI-13) | Prompt `explain@1.0.0` | Handover §7.2; temperature 0.1, max_tokens 900; `evidence_ids` regex `^E\d{1,2}$` in the JSON schema; retry message template. Confidence output kept as strong/moderate/weak (M2 mapping in adapter). |
| A4-02 | Validator (AI-14) | `validation/citations.py` etc., implementing handover §6 in order: (1) schema; (2) ids ⊆ evidence keys, non-empty, same for contradictions; (3) **number check** using A3-04; (4) **entity check** (names/emails/competitors must appear in cited evidence); (5) banned content (pricing/discount recommendations; speculation phrases unless a cited signal quote supports them → move to `unknowns`); (6) summary must only contain numbers from valid claims. Returns `ValidationResult{valid_claims, dropped[{claim, reason}], errors}`. |
| A4-03 | Outcome policy | all valid → pass; ≥2 valid after dropping → pass and log `validation_errors`; <2 valid → retry once with feedback listing exact problems → re-validate → else fallback. Max 1 retry (cost/latency bound). |
| A4-04 | Deterministic injections | Unknowns/contradictions from detectors are always included: if the model omits a detector-provided contradiction/unknown, the pipeline **adds it** (from evidence) so they cannot be skipped (algorithm §7). |
| A4-05 | Fallback explanation | `fallback/templates.py`: one sentence per rule hit with exact numbers and evidence ids ("Usage dropped 38% (E2). Renewal in 43 days (E1)."), mark `needs_review`, no AI drafts. Reuses text patterns agreed with Rajwardhan's `rules/texts.py` (so fallback and template explainer match). |
| A4-06 | Port adapter | `LLMExplainer` implements `Explainer`; returns `ExplanationOut` with `model`, `prompt_version`; fallback returns `model="template"`, `prompt_version="template@1"`. |
| A4-07 | Judge | `evals/judge.py`: entailment prompt ("Does evidence X support claim Y? yes/no/partial"), run with a different/larger model; calibrate against 30 human-labeled claim/evidence pairs before trusting it. |
| A4-08 | Tuning loop | As A2-07; also test thinking on/off, prompt length, evidence ordering effects, temperature 0.0 vs 0.1. |
| A4-09 | Property tests | Hypothesis tests: for random evidence and random model outputs, *no* output that passes the validator contains a number absent from cited evidence or an unknown evidence id (the 100% guarantee). |

**Gate:** raw citation validity ≥ 90%, post-validator 100% (by construction + property test), number fidelity ≥ 98% raw, unsupported-claim rate < 5% (judge + human 30 cases), fallback rate < 10%, p95 < 8 s.
**Failure plan:** fallback rate or unsupported rate over gate → shrink claim count, shorter evidence, 27B model; record in ADR.

---

## Phase A5 — T3 action drafts + action validation (weeks 8–11)

**Goal:** safe, typed proposals that map cleanly to backend payloads; nothing the backend would reject, nothing risky.

| ID | Task | Detail |
|---|---|---|
| A5-01 (AI-15) | Prompt `draft@1.0.0` | Handover §7.3; temperature 0.4, max_tokens 1200; allowed types come from the run context (policy-filtered by backend); health values from field mapping. |
| A5-02 | Post-validation (`validate_actions`) | `validation/actions.py`: contact ids ∈ provided and `is_active` else drop email; field_key mapped else drop; health value ∈ mapped enum; **banned-phrase regex** (`discount|% off|free month|price (cut|reduction)|waive|refund|contract (change|amendment)`) → drop + `policy_drop`; **internal-metric leak** check (numbers matching `rule_metric` evidence in customer email) → set flag `contains_internal_metric` (not drop); evidence ids valid; dedupe against open cards of same finding; max 4 actions; length limits. |
| A5-03 | Mapper (M1) | `adapters/backend_contract.py::to_backend_proposal()`: `to_contact_ids`→emails (from the contacts list given by `/internal/.../contacts`), `due_in_days`→`due_date`, `owner_crm_id` from account context, `associate` refs, `field_key`→real property + `before` from account, `body_text` trimmed, Slack `to=owner|manager`→Slack user id when known else drop. Round-trip test: mapped payload validates against backend `ACTION_PAYLOADS` models (read-only import of the OpenAPI snapshot or a copied schema; contract test). |
| A5-04 | Style hygiene | Email body: 80–160 words, no internal numbers, no pricing, signed as owner first name; unit checks (word count, placeholder leakage like `{{`, language). |
| A5-05 | Port adapter | `LLMActionPlanner` implements `ActionPlanner`; returns list of `ActionProposal` (type, payload, rationale, evidence_keys) after validation + mapping. |
| A5-06 | Injection end-to-end (AI-18) | Hooli case and adversarial set run through T1→T2→T3: assert no proposal includes recipients outside contacts, no field/tier changes, quarantined text never appears in prompts (inspect rendered prompts in tests). |
| A5-07 | T4 `summarize_for_crm` (P1) | Small prompt `crm_note@1.0.0`; same citation rules; optional, after T3 gate. |
| A5-08 | Tuning loop | Rejection-style review: human reads 30 drafts per prompt version, categorizes problems (tone, mention of internal data, wrong person), feeds back into prompt/validator. |

**Gate:** banned phrases after validation = 0, recipient correctness 100%, mapped payloads validate 100%, internal-metric flag precision/recall measured on a labeled set, injection cases 100%.

---

## Phase A6 — Orchestration, observability, versioning (weeks 10–13)

**Goal:** the whole per-account run as a durable graph, fully traced and versioned, with automated eval gates.

| ID | Task | Detail |
|---|---|---|
| A6-01 (AI-16) | State + nodes | `graph/state.py` per handover §4.1; nodes call the plain functions from A2–A5. Backend-owned nodes (`load_evidence`, `run_rules`, `apply_policy`, `execute_tier1`, `record`) are implemented as **client calls** to the internal API (or fakes in tests), never as direct DB access. |
| A6-02 | Edges and timeouts | Edges per §4.2; retry-once loop with error feedback; LLM node timeout 60 s, run budget 5 min (excluding approval wait); node failures route to fallback, not crash. |
| A6-03 | Checkpointing | `AsyncPostgresSaver`, `thread_id = run:{run_id}`. The checkpoint tables are created by the saver in a **separate schema/database owned by the AI service** (avoids touching backend migrations). Restart test: kill worker during `wait_for_approval`, resume, finish. |
| A6-04 | Approval wait | `interrupt({"card_ids": [...]})`; resume with `Command(resume={"decisions": ...})` when the backend reports all Tier 2 cards decided/expired (polling or callback agreed with Vedansh; ADR-007 says graph only does bookkeeping). |
| A6-05 | Idempotency | Same `run_id` re-delivered → no duplicate signals/proposals (use content hashes + backend idempotency); lock per account on our side too. |
| A6-06 (AI-20) | Langfuse | Trace per run; span per node; generation per LLM call with prompt version, token counts, latency, validator result; **masking** of emails/phones; store evidence labels + hashes instead of full bodies. Dashboards: JSON failure rate, validator drop rate, fallback rate, claims per finding, approval rate per prompt version. Alerts: fallback > 20% in 1 h, p95 > 20 s. |
| A6-07 (AI-21) | Versioning | Prompt registry loads `task@x.y.z`, keeps last 2 versions loadable; every output carries `model` + `prompt_version` + `evidence_hash`; `prompt_variant` flag read (from `/me`-style flags via internal API or config) for canary. |
| A6-08 (AI-17 part 2) | CI eval smoke | `ai.yml` job: 5-case smoke using **recorded responses** on every PR touching `revops_ai/prompts|validation|tasks`; nightly full eval job on the staging GPU writing `evals/results/*.json` (file the Admin › Evals page can later read through the backend). |
| A6-09 | Failure drills | LLM down, invalid JSON storm, slow model, backend 5xx, partial run: each produces fallback/needs_review with a recorded run status, never an unhandled exception. |

**Gate:** worker-restart-while-waiting test passes; alerts fire in a staging fault test; smoke eval green in CI; trace for one Acme run shows every node and no raw email bodies.

---

## Phase A7 — Backend integration, external mode (weeks 13–16)

**Goal:** run the same code against the real `/internal/v1` and the real backend data (requires backend Phase 3 data + V6-02).

| ID | Task | Detail |
|---|---|---|
| A7-01 | Internal client | `adapters/internal_client.py` (httpx, `X-Internal-Key`, retries, request ids): context, pending-extraction, save signals/explanation/proposals, run status, contacts. Strict typed responses; honors `rejected[]` and `errors[]` returned by the backend validation. |
| A7-02 | Worker | `adapters/worker.py`: loop/consumer that (a) drains `pending-extraction` → T1 → `save_signals`; (b) for findings needing explanation → context → T2 → `save_explanation`; (c) T3 → `save_proposals`; (d) reports `run status` transitions. Trigger model agreed with Vedansh (poll interval vs webhook/enqueue); concurrency and rate limits per org. |
| A7-03 | Fake backend parity | `tests/fake_backend.py` kept in sync with `openapi.internal.json`; once the real endpoints exist, the same suite runs against a live staging instance (marker `-m staging`). |
| A7-04 | Backend-rejection handling | If backend rejects (recipient not allowed, banned phrase, unknown evidence id, tier blocked) → log as eval signal ("backend disagreed with AI validator"), drop the item, never retry blindly. Target: 0 backend rejections caused by AI-side validator gaps; every occurrence becomes a regression test. |
| A7-05 | Acme full loop on staging | HubSpot sandbox data + usage → rules (backend) → T1 on emails → T2 explanation with ≥4 cited claims, unknowns, contradiction → T3 four proposals → cards created with right tiers → approvals (backend). Record the run in `evals/README.md`. |
| A7-06 | `AI_MODE` switching | Verify flipping `AI_MODE=external` works with our worker running and that stopping it degrades to template/fallback without errors in the backend. |
| A7-07 | Data audit | Verify nothing leaves infra: network policy test / egress check on the AI host; no external LLM URL configured anywhere. |

**Gate (M3 exit from task.md):** Acme finding has ≥ 4 cited claims, unknowns, contradiction; all eval gates pass on the golden set; backend rejection rate from AI proposals < 1%.

---

## Phase A8 — Hardening, canary, handover (weeks 16–18)

| ID | Task | Detail |
|---|---|---|
| A8-01 | Full eval run | All gates in handover §8.2 on the 30-case set; human review of 10 random cases recorded in `evals/reviews/`. |
| A8-02 | Quantization decision | If using FP8/AWQ, rerun the full eval after quantizing; compare latency/GPU memory; pick by gates, not by speed alone. |
| A8-03 | Load/latency | Simulate nightly: 500 accounts × (T2 + T3) + T1 on ~600 new emails; measure throughput with continuous batching; verify the nightly window; tune concurrency and `--max-num-seqs`. |
| A8-04 | Canary | Flag `prompt_variant` at 10% orgs; compare approval rate and "not useful" for one week; promote or roll back by gates. |
| A8-05 | Security review (AI) | Prompt-injection retest, log/trace leakage test (search traces for emails), dependency audit, API key rotation for LLM and internal API. |
| A8-06 | Runbooks | `docs/ai-runbook.md`: model down, high fallback rate, JSON failure storm, bad prompt rollback, GPU out of memory, re-run evals, swap model (skill S11). |
| A8-07 | Documentation | `apps/ai/README.md`, `evals/README.md` (current numbers + known failure patterns), update `aiengineerhandover.md` where reality differs, ADR for each decision made (model, separate package, thresholds). |
| A8-08 | 7-day soak (ALL-01) | Staging with demo + test accounts; no manual fix required. |

---

## Phase A9 — Phase 2: learning from humans (pilot period)

Prerequisites: backend `edit_feedback`, `outcomes`, rejection reasons and dismiss reasons are actually being written (backend P2 tasks). We only **read** them via an API the backend provides (request list at A8).

| ID | Task | Detail |
|---|---|---|
| A9-01 (P2-02) | Edit-diff summarizer | Weekly job: per user, summarize subject/body diffs into 1–3 short preference lines ("removes 'Hope you are well'", "always CCs manager"); validator ensures lines are neutral style notes, no customer facts; injected into T3 prompt under a delimited preferences block. Preferences are shown to the user and can be disabled (UI is frontend's job; we expose data only). |
| A9-02 | Rejection analysis | Per action type + rule: `wrong_action` > 40% over ≥ 20 cards → emit a *suggestion* (not an automatic change). |
| A9-03 | Threshold suggestions (P2-03 support) | From dismiss reasons / "not useful" feedback; math in `algorithm.md` §17; AI side provides analysis notebooks/jobs only if backend asks; default owner is backend. |
| A9-04 | Outcome-aware ranking | Rank action templates by reply/meeting outcomes per finding type; used as soft hints in T3 prompt after A/B evidence. |
| A9-05 | Golden set → 200 (P2-10) | Anonymized pilot cases with written consent; consistent replacement of names/emails/domains; reviewed twice; stored outside git if contractual. |
| A9-06 | Guardrails | No silent self-modification: every learned item is versioned, visible, reversible; evals re-run when preference injection is on. |

---

## Phase A10 — Phase 3: churn probability model (only with real data)

Entry criteria (hard): ≥ 12 months of history, ≥ 300 renewals with known outcomes, written consent.

| ID | Task | Detail |
|---|---|---|
| A10-01 | Dataset build | Point-in-time features at 90 days before renewal (usage slopes 4/8/12 wk, seat utilization, days since meeting/reply, active contacts, champion change, signal counts 30/90 d, tickets, payment failures, ARR, plan, tenure, renewal count, rule-hit history). Leakage tests: no feature uses data after the snapshot date. |
| A10-02 | Baselines | Logistic regression on a few features, then the current rules-severity as a baseline; the model must beat both. |
| A10-03 | Model | LightGBM + isotonic/Platt calibration; time-based split (older train, newer test); per-segment (SMB vs mid-market) evaluation. |
| A10-04 | Metrics | AUC-PR, Brier, calibration curve, top-decile lift. |
| A10-05 | Explainability | SHAP top features turned into evidence items (cited, validated) so the existing explanation pipeline stays the only text path. |
| A10-06 | Release rule | Show probability only if calibration error < 0.05 on holdout; else keep High/Medium/Low. Fairness: account-level features only, no individual-employee features beyond role. |
| A10-07 | Serving | Batch scoring job exposing a score through the same internal API pattern (backend adds field); model card + monitoring for drift. |

---

## 3. Cross-cutting rules for every phase

**Workflow per task (superpower.md):** understand → plan (short) → failing test/fixture first → build small → run eval/tests → self-review against the hard-rule checklist → note numbers in `evals/README.md`.

**Hard-rule checklist (every PR):** no tools given to the LLM · every AI sentence has valid evidence ids · untrusted text only inside delimiters · recipients only by contact id then mapped from the allowlist · Tier 3 never proposed as executable · prompt change = new version + eval table in PR · no customer data in logs/traces/fixtures · no external AI API.

**Prompt change protocol:** copy `task.old.md` → `task.new.md`; semver (patch wording, minor behavior/field, major schema); update schema+validator+adapter; full eval vs previous; table in PR; 10 human-reviewed outputs; canary via `prompt_variant`.

**Eval gates (promotion criteria):** JSON validity ≥ 99.5% · citation validity after validator 100% · raw ≥ 90% · number fidelity ≥ 98% · unsupported < 5% · fallback < 10% · signals P ≥ 0.85/R ≥ 0.70 · injection 100% · banned phrases 0 · recipients 100% · p95 T2 < 8 s.

**Reviews:** validator, prompts, and graph changes get a second reviewer who did not write them. Backend owners review `adapters/backend_contract.py` changes.

---

## 4. Risk register (AI side)

| Risk | Likelihood | Impact | Mitigation | Phase |
|---|---|---|---|---|
| Exact model version unavailable / unclear | Medium | Medium | Qwen3.5-9B default, 27B fallback, ADR, eval-driven choice | A0 |
| 9B model fails citation/number gates | Medium | High | Validator + fallback by design; shorter evidence; 27B; two-pass; tuning loop | A4 |
| Recall of T1 too low | Medium | Medium | Prompt iteration, thinking mode, 27B; rules still work without signals | A2 |
| Backend evidence format differs from reference | Medium | High | Conformance suite + weekly sync; refuse to prompt on non-conformant evidence | A3/A7 |
| Contract drift in `/internal/v1` | Medium | Medium | OpenAPI-snapshot contract test in CI | A0+ |
| Backend `/internal/v1` arrives late (Phase 6) | High | Medium | In-process adapter + fake backend; work is not blocked | A6/A7 |
| Prompt injection gets through | Low | Critical | Layers: prefilter, schema, id-based recipients, backend allowlist/tier, human approval; adversarial set at 100% | A2/A5 |
| LLM judge unreliable | Medium | Medium | Calibrate against human labels; human review of 10/30 cases remains | A4 |
| GPU cost/availability | Medium | Medium | Single 24 GB GPU, quantization after eval, nightly batching | A0/A8 |
| Trace/log data leakage | Low | High | Masking + hash-only storage + automated leakage test | A6/A8 |
| Checkpoint DB ownership unclear | Low | Medium | Separate schema owned by AI service; agree with Vedansh early | A6 |

---

## 5. Immediate next steps (first 5 working days)

1. Get the exact model decision (founder question) and a GPU/Ollama endpoint → A0-01/02.
2. Create `apps/ai/` skeleton, CI file, and `FakeLLM` → A0-04/05.
3. Run the structured-output smoke (A0-03) and write numbers to `evals/README.md`.
4. Send Vedansh + Rajwardhan the **mismatch table (§0.3)** and the **dependency requests (§0.4)** as one short message; ask for a 30-min sync to confirm D1–D3.
5. Start A1-01/02: fixture format + the six seed stories.

## 6. Open questions (need a human decision)

1. Is a separate `apps/ai` package acceptable to the team (D1), or must the code live under `apps/api/app/agent` and `llm` (which requires the backend owners to relax the AI-import test)?
2. Who triggers AI runs in external mode: AI worker polls the internal API, or backend enqueues/calls us? (Needs agreement with Vedansh before A7.)
3. Where do LangGraph checkpoints live (separate DB/schema owned by AI vs the shared Postgres)?
4. Final model/GPU budget and region (India vs US) for staging.
5. Who owns the shared golden fixtures (AI vs Rajwardhan's R3-09) — recommendation: one repository location, AI owns text/signal expectations, Rajwardhan owns rule expectations.
