# thinking.md — Decisions, Reasoning and Trade-offs

> Why the product and system look the way they do. Each decision is an ADR (Architecture/Product Decision Record): context → decision → why → trade-off → revisit when.
> If you want to change a decision, add a new ADR that supersedes the old one. Do not silently edit.

---

## Part A — Product thinking

### A1. The problem is trust, not detection
Risk detection is crowded (Gong, Gainsight Staircase + Atlas, Salesforce Agentforce + Momentum, HubSpot Agent Hub, Salesloft + Clari, Rox, Oliv AI). What is missing in one affordable, CRM-neutral tool is the combination of: (1) signals merged from many sources, (2) every claim cited to a source record, (3) actions reviewed like a diff before approval, (4) a permanent "why" record. Gartner names "inadequate risk controls" as a reason >40% of agentic AI projects will be cancelled by 2027. **So we compete on trust.** "Better health score" is not our pitch.

### A2. Fewer, better alerts
Alert fatigue kills CS tools. The Today page targets 3–7 accounts per user, not 50. Low-severity findings stay in Accounts, not Today. Every finding must earn its place with evidence.

### A3. Honest uncertainty is a feature
Showing "Not confirmed" and "Signals that disagree" makes the tool more believable, not less. A tool that is always confident will be caught being wrong once and then ignored.

### A4. Expansion matters as much as churn
Benchmarks say expansion is 40–50% of new ARR. A tool that only cries "risk" is a cost center; one that also finds upsell is a revenue tool.

### A5. Who we are not for (yet)
Enterprise Salesforce shops with Gainsight budgets. We start with HubSpot SMB/mid-market SaaS (many in India and globally) where enterprise suites are too heavy.

### A6. Things that sound good but we said no to (for now)
| Idea | Why not now |
|---|---|
| Churn probability % | No outcome data yet → any % is fake precision. Phase 3. |
| Fully autonomous emails | Kills trust; legal/brand risk. Drafts + approval. |
| Our own CRM | Users won't migrate. Sit on top. |
| Meeting recorder / call transcripts | Separate hard product; competitors strong. Maybe ingest from Fathom/Fireflies later. |
| B2C retention | Different data shape, volume, buyers. Phase 3 decision. |
| Multi-agent "crew" architecture | More moving parts, harder to debug. One graph with clear nodes. |

---

## Part B — Architecture Decision Records

### ADR-001 — Python FastAPI backend + Next.js frontend
- **Context:** Founder's skill set (Python, React); AI ecosystem is Python-first.
- **Decision:** FastAPI (async) + Pydantic v2; Next.js App Router frontend.
- **Why:** Typed models shared via OpenAPI; LangGraph, vLLM client, Google/HubSpot/Slack SDKs all Python-native.
- **Trade-off:** Two languages; type sync needed → `openapi-typescript`.
- **Revisit:** never for v1.

### ADR-002 — Monolith + workers, not microservices
- **Decision:** One API service, one worker image with multiple queues, Postgres, Redis, model server.
- **Why:** 1–3 developers; fewer deploy/debug surfaces.
- **Revisit:** when one queue's load needs separate scaling beyond worker count, or team > 8.

### ADR-003 — PostgreSQL as the only system of record (+ RLS)
- **Decision:** Postgres for app data, LangGraph checkpoints, decision log; Row Level Security for tenancy.
- **Why:** One backup/restore story; transactions across finding + card + log; RLS protects against app bugs leaking data across tenants.
- **Trade-off:** Must remember `SET LOCAL app.org_id` in every session (enforced by session helper + test).
- **Alternatives rejected:** separate vector DB (not needed in v1), MongoDB (weak for relational joins + audit).

### ADR-004 — Rules decide, LLM explains
- **Decision:** Deterministic rules create findings; LLM only extracts signals from text, explains, drafts.
- **Why:** Rules are stable, testable, explainable, cheap; small model is unreliable as a judge of risk; regulators and users can understand rules.
- **Trade-off:** Misses patterns rules don't encode → Phase 3 ML ranking.
- **Revisit:** when outcome data supports a calibrated model.

### ADR-005 — Self-hosted Qwen ~9B via vLLM
- **Context:** Customer email + CRM data is sensitive; cost must be predictable; founder chose Qwen 9B.
- **Decision:** Self-host Qwen ~9B (exact version TBD; Qwen3.5-9B closest verified) with vLLM, `guided_json` outputs.
- **Why:** Data stays in our infra; open license (Apache 2.0 for Qwen3.5-9B per reports); schema-constrained output makes a small model usable.
- **Trade-off:** Lower reasoning quality than frontier models → mitigated by small tasks, numbered evidence, validator, fallback. GPU ops burden.
- **Revisit:** if raw citation validity < 90% or unsupported-claim rate > 5% on golden set → try Qwen3.8-27B; if still failing, consider a private-deployment frontier model with a DPA.

### ADR-006 — LangGraph for orchestration
- **Decision:** LangGraph with `interrupt()` + Postgres checkpointer.
- **Why:** Durable pause/resume for human approval across restarts; explicit graph = debuggable; `approve/edit/reject` pattern maps to our cards.
- **Alternatives:** Pydantic AI (great typing, deferred approvals) — may use Pydantic models inside nodes anyway; CrewAI (less precise control); plain Celery state machine (possible, but we'd rebuild checkpointing).
- **Trade-off:** Framework churn; keep business logic in plain functions so nodes are thin wrappers.

### ADR-007 — Approval is per card; executor triggered by the API
- **Context:** One run proposes several cards; users decide at different times, from web or Slack.
- **Decision:** Approve endpoint updates the card and enqueues `execute_card` directly. The graph's interrupt only waits for "all cards decided/expired" to close the run and record.
- **Why:** Avoids complex partial resumes; executor stays independent and idempotent; Slack's 3-second ack rule is easy to meet.
- **Trade-off:** Graph is less "pure"; run completion is bookkeeping.

### ADR-008 — The LLM never gets write tools; HubSpot MCP is not given to the model
- **Context:** HubSpot's official remote MCP executes writes immediately with no reviewable plan.
- **Decision:** Executor uses REST APIs (official SDK) after approval. MCP may be used later only for **read** exploration, never for writes by the model.
- **Why:** Guarantees approval-native behavior and prompt-injection safety.

### ADR-009 — Connectors: direct SDKs first, Composio optional
- **Context:** Earlier plan said "start with Composio for speed". We need sync cursors, raw payloads, webhooks, exact pre-images for undo.
- **Decision:** HubSpot, Gmail, Calendar, Slack via official SDKs behind a `Connector` interface. Composio adapter allowed for prototypes and long-tail tools.
- **Why:** Full control of incremental sync and idempotency; no extra vendor in the data path for core sources; costs predictable.
- **Trade-off:** More code for OAuth/refresh/rate limits.
- **Revisit:** when adding 5+ long-tail connectors.

### ADR-010 — Gmail drafts, not sends, in v1
- **Decision:** `email_draft` creates a Gmail draft; "send" behind feature flag.
- **Why:** Human remains the sender; reduces brand and legal risk; still saves most of the time.
- **Trade-off:** Outcome tracking must detect the sent message later.
- **Note:** Gmail read/compose scopes are restricted → OAuth verification + annual security assessment (CASA) before public launch; Testing mode/internal until then. Plan time and cost for this.

### ADR-011 — Evidence IDs + server-side validator (not "trust the prompt")
- **Decision:** Model must output `evidence_ids`; code checks IDs, numbers, names; invalid claims are dropped; fallback template if too few remain.
- **Why:** Prompt instructions alone are not enough for a 9B model; validation makes "every claim is cited" a guarantee.

### ADR-012 — Tiered autonomy with locked Tier 3
- **Decision:** Tier 1 auto (internal, reversible), Tier 2 one click, Tier 3 blocked (pricing, discounts, contract, deal amount/stage/close date, deletes). Admins can raise tiers; can't lower locked ones.
- **Why:** Matches mature industry pattern (Oliv review-by-default, Gainsight "configurable autonomy") and the PS safety requirement.

### ADR-013 — Append-only, hash-chained decision log
- **Decision:** Insert-only table, DB grants deny UPDATE/DELETE, per-org hash chain.
- **Why:** Audit trust; easy integrity check; supports "why replay".
- **Trade-off:** Corrections are new entries, never edits.

### ADR-014 — Celery + Redis for jobs
- **Decision:** Celery with separate queues; Beat for schedules.
- **Why:** Mature, retries, routing, widely known. arq is lighter but fewer features; Temporal is powerful but heavy for v1.
- **Revisit:** if workflows become long-running multi-step with complex retries → Temporal.

### ADR-015 — Auth.js on the web + short-lived service JWT to API
- **Decision:** Auth.js handles login; Next route handlers mint 5-minute JWTs for FastAPI.
- **Why:** Browser never holds API tokens; FastAPI stays stateless; easy to swap to Clerk later.
- **Trade-off:** All API calls go through Next proxy (slight latency) — acceptable.

### ADR-016 — SSE, not WebSockets
- **Why:** One-way updates (card executed, run finished) are enough; SSE works through proxies and is simple.

### ADR-017 — No pgvector in v1
- **Why:** Evidence comes from structured SQL + recent events; semantic search not needed yet.
- **Revisit:** "Ask about this account" chat or long-history retrieval.

### ADR-018 — Priority score is a transparent formula
- **Decision:** Weighted formula (severity, urgency, value, confidence) × freshness; breakdown shown in UI.
- **Why:** Users trust what they can inspect; tune later with outcome data.

### ADR-019 — Synthetic golden dataset before real data
- **Decision:** 30 synthetic accounts (incl. Acme and Globex stories, injection case) as fixtures for rules + AI evals.
- **Why:** Repeatable tests, safe for CI, no customer data.

### ADR-020 — Monorepo
- **Decision:** `apps/web`, `apps/api`, `infra/`, shared docs at root.
- **Why:** One PR can change API + types + UI together.

---

## Part C — Risks and how we think about them

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Small model hallucinates / breaks format | Medium | High | guided_json, validator, fallback, evals, bigger-model fallback (ADR-005) |
| Gmail restricted-scope verification delays launch | High | High | Start verification early; launch pilot in Testing mode (≤100 users) or internal-only; HubSpot-logged emails as partial substitute |
| Bad CRM data (missing renewal dates, owners) | High | Medium | Unknowns list, onboarding field-mapping preview, data-quality hints |
| Alert fatigue | Medium | High | Severity thresholds, Today cap, dismiss reasons → rule tuning |
| Prompt injection via email | Medium | High | Defense layers (aiengineerhandover §7.4), executor re-checks |
| Duplicate/incorrect writes to CRM | Low | High | Idempotency, pre-image check, stale-preview stop, revert |
| Incumbents copy features | High | Medium | Speed, price, CRM-neutral, trust UX; focus on underserved SMB/India |
| GPU cost/ops | Medium | Medium | One GPU for v1; batch nightly; quantization after eval |
| Tenant data leak | Low | Critical | RLS + tests + separate admin role |

---

## Part D — Open questions (decide soon)

1. Exact Qwen model version and GPU provider (and India vs US region).
2. Draft-only vs send in v1 (default: draft).
3. Pricing model (per seat / per account / % of saved ARR) — Phase 3, but affects data we log.
4. Whether to ingest HubSpot-logged emails only (no Gmail scopes) for first pilots to avoid verification delay.
5. Product name and domain.

---

## Part E — How to think when unsure (team heuristics)

- If an AI output can reach a customer or change a record → it needs evidence, validation, and a human click.
- If a feature cannot show its evidence → it doesn't ship.
- Prefer a boring rule that is right 80% of the time and explainable over a clever model that is right 85% and opaque — until we have outcome data.
- When in doubt, show less on Today.
- Every number on screen must be traceable to a row in the database.
