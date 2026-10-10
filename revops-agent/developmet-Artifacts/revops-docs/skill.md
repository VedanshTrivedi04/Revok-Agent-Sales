# skill.md — Repeatable Playbooks (Skills)

> Step-by-step recipes for the changes we make again and again. Humans and AI coding agents should follow these exactly so every change keeps the hard rules in `agent.md` §3.
> Each skill: **When to use → Steps → Files touched → Checks.**

---

## Index

| # | Skill | Owner |
|---|---|---|
| S1 | Add a new risk/expansion rule | BE (+AI for golden cases) |
| S2 | Add a new action card type | BE + FE + AI |
| S3 | Add a new connector (data source) | BE |
| S4 | Add a new signal kind (AI extraction) | AI |
| S5 | Change or add a prompt | AI |
| S6 | Add a new API endpoint | BE |
| S7 | Add a new page / screen | FE |
| S8 | Add a new tenant table (migration + RLS) | BE |
| S9 | Add a golden test case | AI + BE |
| S10 | Debug "why did the agent say/do this?" | Anyone |
| S11 | Swap or upgrade the LLM | AI |
| S12 | Handle an integration outage / re-auth | BE / Ops |
| S13 | Release to production | Ops |
| S14 | Respond to a data-deletion request | Ops |

---

## S1. Add a new rule

**When:** a new churn/expansion pattern should create or strengthen findings.
**Steps**
1. Write the rule spec in `algorithm.md` §4 (key, category, condition, default params, severity points, metrics).
2. Pick key: next free `Rnn_snake_name` or `Xnn_snake_name`.
3. Implement in `apps/api/app/rules/risk.py` or `expansion.py` as a pure function:
   ```python
   @rule("R12_ticket_spike", category="support", finding_type="risk")
   def ticket_spike(ctx: AccountContext, p: TicketSpikeParams) -> RuleHit | None: ...
   ```
4. Add params model + defaults in `rules/defaults.py` (Pydantic with min/max → becomes `params_schema` for the settings UI).
5. Add human text template in `rules/texts.py` (used in evidence labels and UI): `"Tickets in 14 days: {count} (normal {avg})"`.
6. Return `evidence_refs` pointing to the rows that prove it.
7. Add unit tests (fires / doesn't fire / edge cases: missing data, boundary values).
8. Add/adjust ≥ 1 golden case (S9).
9. If it needs new data (e.g., tickets), do S3 first.
**Checks:** `pytest -m golden` unchanged for other cases; rule appears in Settings › Rules with params form; preview endpoint returns count.

## S2. Add a new action card type

**When:** the agent should be able to propose a new kind of action.
**Steps**
1. Decide tier default and whether it is revertable; add to `algorithm.md` §9 and §12.
2. BE: payload model in `schemas/action_payloads.py`; add to `ActionType` enum + CHECK constraint migration.
3. BE: executor handler `executor/handlers/<type>.py` implementing `find_existing`, `pre_image`, `apply`, `revert` (or `NotRevertable`).
4. BE: policy defaults in `services/policy.py`; allowlist checks in executor.
5. AI: add proposal model to `DraftOutput` union, update `draft@` prompt allowed types, post-validation rules; bump prompt version (S5).
6. FE: preview + edit component in `components/cards/<Type>Card.tsx`; add icon and label; add to Inbox type filter.
7. Slack: Block Kit preview in `slack/blocks.py`.
8. Tests: payload validation, executor idempotency (call twice → one external object), revert, E2E approve flow.
**Checks:** Tier 3 types never executable; card shows evidence chips; log entries for proposed/approved/executed/reverted.

## S3. Add a new connector

**When:** new data source (e.g., Zendesk, Stripe, Salesforce).
**Steps**
1. Write a short design note: objects to read, how they map to `accounts/contacts/deals/events/usage`, sync cursor, rate limits, scopes, whether writable.
2. Add provider to `integrations.provider` CHECK + `ProviderEnum`.
3. Implement `connectors/<provider>.py` with `Connector` interface (`test_connection`, `sync`); `WritableConnector` only if the executor needs it.
4. OAuth: add to `routes/oauth.py` (authorize URL, token exchange, refresh) or API-key flow.
5. Mapping functions are pure (`map_ticket_to_event(raw) -> EventIn`) and tested with recorded fixtures in `tests/fixtures/<provider>/`.
6. Register in `connectors/registry.py`; add Beat schedule.
7. Entity resolution: make sure new events get `account_id` (see `algorithm.md` §1).
8. FE: integration card in Settings › Integrations + onboarding step if core.
9. Update `research.md` (limits/compliance) and `spec.md` FR list.
**Checks:** no LLM import in connector; tokens encrypted; incremental sync resumes from cursor; 429 handling tested; data appears on account timeline.

## S4. Add a new signal kind

**Steps**
1. Add kind to `Signal.kind` Literal (AI) and `signals.kind` CHECK (BE).
2. Update `extract@` prompt definitions (one line, plain words); bump version.
3. Add ≥ 3 golden messages (positive, negative, tricky).
4. Decide which rule consumes it (S1) — a signal alone never creates a finding.
5. FE: label + icon in timeline signal badges.
**Checks:** extraction P/R gates still pass; quotes are exact substrings.

## S5. Change or add a prompt

**Steps**
1. Copy `prompts/<task>.<old>.md` → `<task>.<new>.md` (semver: patch = wording, minor = new field/behavior, major = schema change).
2. Edit; keep untrusted text in delimiters; keep "use only the evidence" and "return JSON only".
3. If schema changes, update Pydantic model + validator + BE storage.
4. Run `python -m app.evals.run --prompts <task>@<new>` on full golden set; compare with previous version.
5. Paste metrics table into PR; human-review 10 outputs.
6. Roll out behind flag `prompt_variant` → compare approval rate / "not useful" for a week → promote.
**Checks:** gates in `aiengineerhandover.md` §8.2 pass; old version still loadable.

## S6. Add a new API endpoint

**Steps**
1. Define request/response Pydantic models in `schemas/`.
2. Route in `routes/<area>.py` with `response_model`, role dependency (`require_role`), and `org_session`.
3. Logic in `services/`; state changes write `decision_log` in the same transaction.
4. Errors via `AppError` codes; document in OpenAPI `responses`.
5. Tests: happy path, permission denied, cross-tenant access returns 404.
6. Regenerate FE types (`pnpm gen:api`).
**Checks:** endpoint listed in `backenddeveloper.md` §5.3 (update the table).

## S7. Add a new page

**Steps**
1. Add page spec to `frontenddeveloper.md` (purpose, fields with source, actions, states, permissions).
2. Create route under the right portal group; use layout components.
3. Data via typed client + TanStack Query keys (add to `lib/query-keys.ts`); SSE invalidation if live.
4. Build loading skeleton, empty state, error state.
5. Permission gating via `can()`.
6. Mobile check if it's Today/Inbox/Finding/Card.
7. Tests: component tests for logic; E2E if it's part of a main flow.
**Checks:** no hand-written API types; a11y lint passes; severity/tier labels have text.

## S8. Add a new tenant table

**Steps**
1. SQLAlchemy model with `org_id` (FK organizations, indexed) + timestamps.
2. Alembic migration: create table; **enable + force RLS + policy** (use helper `apply_tenant_rls(op, "table")`).
3. Grants for app role (no UPDATE/DELETE if append-only).
4. `test_rls.py` auto-checks all tables with `org_id` — run it.
**Checks:** migration up/down tested on a copy of staging data.

## S9. Add a golden test case

**Steps**
1. Create folder `tests/golden/cases/<nn>_<name>/` with `account.json`, `events.jsonl`, `usage.json`, `expected.json` (see `aiengineerhandover.md` §8.1).
2. Use synthetic names/domains (`*.example`), dates relative to a fixed `now` in the fixture.
3. Record LLM responses for CI (`--record`), keep them in `recorded/`.
4. Run `pytest -m golden -k <name>`.
**Checks:** case covers one clear behavior; expected values explained in `README.md` of the case.

## S10. Debug "why did the agent say/do this?"

1. Open the finding → History → log entry → **Why replay** (`/log/<id>`).
2. Check evidence snapshot: is the source data right? (If not → connector/entity resolution bug.)
3. Check rule metrics: do numbers match the data? (If not → rule/context bug, `algorithm.md` §3–4.)
4. Check model output + validator result (Runs › run → Langfuse trace).
5. If a claim is wrong but cited → add a golden case reproducing it; fix prompt or validator; bump version.
6. If a card executed wrongly → check executor logs + `executions.request/response`; use Revert; file incident note.

## S11. Swap or upgrade the LLM

1. Deploy new model on staging vLLM (separate port).
2. Run full evals with `--model <new>`; compare all gates + latency + GPU memory.
3. If quantizing, run evals again after quantization.
4. Canary via `LLM_MODEL` per-org flag; monitor fallback rate and approval rate for 1 week.
5. Update `thinking.md` ADR-005 (new ADR if decision changes) and `aiengineerhandover.md` §2.

## S12. Integration outage / re-auth

1. Integration status → `needs_reauth` or `error`; banner shows automatically.
2. For token revocation: notify admin/user (in-app + Slack), they click Reconnect.
3. For provider outage (5xx/429 storms): sync backs off; nothing to do; findings show "data last updated …" unknown.
4. After recovery: trigger "Sync now"; Gmail history expired → automatic 30-day resync.
5. Never fake data or skip validator to "keep the list full".

## S13. Release to production

1. CI green on `main` (lint, tests, golden, E2E smoke, build).
2. Check migrations: backward compatible (expand → migrate → contract over two releases for breaking changes).
3. Deploy: run `alembic upgrade head` → restart API → restart workers (drain `executor` queue first) → deploy web.
4. Smoke: `/health/ready`, login, Today loads, approve a card on the demo org.
5. Watch Sentry + LLM dashboard for 30 minutes. Roll back image tag if error rate spikes.

## S14. Data-deletion request

1. Owner deletes org (Settings › Data) or support ticket verified by owner email.
2. System: soft delete → revoke OAuth tokens at providers → stop jobs.
3. After 30 days, purge job hard-deletes all rows with `org_id` (including Langfuse traces by org tag) and writes a final `system` log entry outside the org (platform audit).
4. Confirm by email to owner.
