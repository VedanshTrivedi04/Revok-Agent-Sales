# spec.md — Product Specification

> Working name: **RevOps Agent** (final name TBD; options: Pramaan, Proofline, Nazar, Sakshi). Repo slug: `revops`.
> Owner: Vedansh Trivedi · Status: v1 spec · Last updated: 2026-10-10
>
> This is the single source of truth for **what** we build. `systemdesign.md` says **how it fits together**, the three handover files say **how each role builds it**, `task.md` says **in what order**.

---

## 1. One-line definition

An **evidence-first, approval-native Revenue Risk & Action Platform** for B2B SaaS teams. It joins CRM, email, calendar and product-usage data into one timeline per customer, finds churn risk and expansion opportunity, explains every finding with cited source records, prepares the next action, and executes it **only after a human approves**. Every decision is recorded.

## 2. Problem

- Customer signals are scattered across CRM, Gmail, Calendar, product analytics, support and billing. Each tool has its own ID for the same customer.
- A CSM/AM with 50–100 accounts cannot review every account every day, so risk is noticed late (often in the weekly meeting, after the customer has already decided).
- Health scores are black boxes ("Health = 42") with no reason and no next step. Rule-based alerts fire too often and are ignored.
- AI agents that write straight into the CRM are not trusted. HubSpot's official MCP server executes writes immediately with no reviewable plan.
- Gartner (June 2025): over 40% of agentic AI projects will be cancelled by end of 2027; "inadequate risk controls" is one of the three named reasons.

Details and sources: `research.md`.

## 3. Goals and non-goals

### Goals (v1 = Phase 1)
1. Every morning, each user sees a **short priority list** (target: 3–7 accounts) instead of 50–100.
2. Every finding shows **why**, with each claim linked to a real source record (email, meeting, CRM field, usage snapshot).
3. Every finding shows **unknowns** (missing data) and **contradictions** (signals that disagree).
4. Every finding comes with **ready actions** (email draft, CRM task, CRM field change with before/after, internal Slack message).
5. Nothing customer-facing or record-changing happens without **one-click human approval**. Pricing/contract actions are **blocked**.
6. Every step is written to an **append-only decision log**; CRM changes can be **reverted**.
7. Detect **expansion** (seat saturation, usage growth, upgrade intent), not only risk.

### Non-goals (v1)
- Churn **probability** (%) from ML — Phase 3, only after real outcome data exists.
- B2C retention module — Phase 3.
- Salesforce and >5 integrations — Phase 3.
- Real-time streaming — nightly + hourly batch + webhooks is enough.
- Pricing plans and billing — Phase 3.
- Sending email automatically. v1 creates **Gmail drafts** or sends only after explicit approval.
- Replacing the CRM. We sit on top of it.

## 4. Users and personas

| Persona | Role in app | Main job | What they need from us |
|---|---|---|---|
| **Priya — CSM / Account Manager** | `member` | Keep accounts healthy, renew, upsell | Daily list, evidence, ready drafts, one-click approve |
| **Rahul — Sales rep / AE** | `member` | Expansion deals on existing accounts | Expansion signals with proof, outreach drafts |
| **Meera — CS/RevOps Manager** | `manager` | Team coverage, renewal forecast, process | Team view, approval of high-impact items, rules and autonomy settings |
| **Arjun — Founder/Admin** | `owner` / `admin` | Set up tool, connect systems, control data | Fast onboarding, integrations, members, data controls |
| **Viewer (CRO, finance)** | `viewer` | Read-only visibility | Lists, findings, log; cannot approve |
| **Platform superadmin (us)** | `superadmin` (internal portal) | Run the service | Tenant health, jobs, model health, evals |

Buyer: B2B SaaS companies (roughly 20–500 accounts per CS team) that cannot afford or do not want an enterprise CS suite. First CRM: HubSpot.

## 5. Core concepts (glossary — use these exact names in code)

| Term | Meaning | Table |
|---|---|---|
| **Organization (org)** | A customer company of ours (a tenant). | `organizations` |
| **Member** | A user inside an org with a role. | `users`, `memberships` |
| **Integration** | A connected source/destination (HubSpot, Gmail, Calendar, Slack, Usage API). | `integrations` |
| **Account** | One of the org's customers (e.g., Acme Corp). | `accounts` |
| **Contact** | A person at an account. | `contacts` |
| **Deal** | A CRM deal linked to an account (renewal, expansion, new). | `deals` |
| **Event** | One item on an account's timeline (email, meeting, note, stage change, usage snapshot…). Always points to its source record. | `events` |
| **Usage snapshot** | Product usage for one account for one period. | `usage_snapshots` |
| **Signal** | A fact extracted from an event by AI (sentiment, competitor mention, champion leaving…). | `signals` |
| **Rule hit** | A deterministic rule that fired for an account, with the numbers it used. | `rule_hits` |
| **Finding** | A risk or expansion conclusion for an account: severity, explanation with citations, unknowns, contradictions. | `findings` |
| **Evidence item** | A numbered item (`E1`, `E2`…) attached to a finding, pointing to an event / usage snapshot / CRM field / signal. | `finding_evidence` |
| **Action card** | A proposed action (email draft, CRM task, CRM field update, CRM note, internal Slack message, meeting request) with preview, tier and status. | `action_cards` |
| **Tier** | Autonomy level: 1 = auto, 2 = one-click approval, 3 = blocked. | `autonomy_policies` |
| **Execution** | One attempt to run an approved card, with request/response and pre-image for undo. | `executions` |
| **Decision log entry** | Append-only, hash-chained record of every important event. | `decision_log` |
| **Agent run** | One run of the agent graph for one account. | `agent_runs` |
| **Outcome** (Phase 2) | What happened after an action (reply, meeting booked, usage change, renewal). | `outcomes` |

## 6. Functional requirements

IDs are referenced in `task.md`. Priority: **P0** = v1 must, **P1** = v1 should, **P2** = Phase 2, **P3** = Phase 3.

### 6.1 Accounts, auth, tenancy
| ID | Requirement | P |
|---|---|---|
| FR-01 | Sign up / log in with Google or email magic link. | P0 |
| FR-02 | Create an organization; creator becomes `owner`. | P0 |
| FR-03 | Invite members by email with a role; invite expires in 7 days. | P0 |
| FR-04 | Roles: `owner`, `admin`, `manager`, `member`, `viewer` with permissions in §8. | P0 |
| FR-05 | A user can belong to more than one org and switch between them. | P1 |
| FR-06 | Data of one org is never visible to another (enforced in DB with Row Level Security). | P0 |

### 6.2 Integrations and data
| ID | Requirement | P |
|---|---|---|
| FR-10 | Connect HubSpot (OAuth). Read companies, contacts, deals, engagements (notes, meetings, emails, tasks), owners. | P0 |
| FR-11 | Connect Google per user (OAuth): Gmail (read + create drafts) and Calendar (read). | P0 |
| FR-12 | Usage data via (a) REST ingest API with org API key, (b) CSV upload with column mapping. | P0 |
| FR-13 | Connect Slack workspace (OAuth); link each member to their Slack user. | P1 (P0 for approvals in Slack) |
| FR-14 | Field mapping: choose which HubSpot properties hold renewal date, ARR/MRR, seats purchased, plan, health/risk field to write back. | P0 |
| FR-15 | Initial backfill (default 180 days of email/calendar, all CRM records) and incremental sync (hourly CRM, hourly Gmail/Calendar, nightly full rule run). | P0 |
| FR-16 | Entity resolution: map emails/meetings/usage to accounts by domain and contact email; ambiguous matches go to a review queue. | P0 |
| FR-17 | Integration health: last sync time, last error, re-connect button; tokens refreshed automatically. | P0 |
| FR-18 | Support tickets (Zendesk/Intercom/HubSpot tickets) and billing (Stripe) signals. | P2 |
| FR-19 | Salesforce connector. | P3 |

### 6.3 Detection
| ID | Requirement | P |
|---|---|---|
| FR-20 | Run deterministic risk rules (R01–R11) and expansion rules (X01–X05) per account; parameters editable per org. See `algorithm.md`. | P0 |
| FR-21 | Compound severity: rule hits from 3+ different signal categories → `high`. | P0 |
| FR-22 | AI signal extraction from new emails and CRM notes: sentiment, competitor mention, champion leaving, pricing/budget concern, escalation, upgrade intent, feature request. | P0 |
| FR-23 | Priority score per finding (value × urgency × severity × confidence). | P0 |
| FR-24 | Dedupe: same account + same finding type is updated, not duplicated; dismissed findings cool down 14 days unless severity rises. | P0 |
| FR-25 | Manual "Run now" for one account. | P1 |

### 6.4 Explanation
| ID | Requirement | P |
|---|---|---|
| FR-30 | Each finding has a short summary and a list of claims; every claim cites ≥1 evidence ID. | P0 |
| FR-31 | Server-side validator rejects any claim with no or unknown evidence ID; one retry, then mark `needs_review`. | P0 |
| FR-32 | Evidence chips open the source (HubSpot record URL, Gmail thread link, Calendar event link, usage chart). | P0 |
| FR-33 | Unknowns list (e.g., "No product usage connected", "Reason for usage drop not confirmed"). | P0 |
| FR-34 | Contradictions list (e.g., "CRM health = Green but usage −40%"). | P0 |
| FR-35 | "What changed since last week" diff on the finding. | P1 |

### 6.5 Actions and approvals
| ID | Requirement | P |
|---|---|---|
| FR-40 | Action card types: `email_draft`, `crm_task`, `crm_field_update`, `crm_note`, `slack_internal`, `meeting_request`. | P0 (`meeting_request` P1) |
| FR-41 | Every card shows tier, preview, evidence it is based on, and for CRM updates a field-level before → after diff. | P0 |
| FR-42 | Approve / Edit then approve / Reject (with reason) from web inbox. | P0 |
| FR-43 | Approve / Reject from Slack (Block Kit buttons); "Edit" opens the web card. | P1 |
| FR-44 | Tier policy: Tier 1 auto-executes (internal, reversible); Tier 2 needs one click; Tier 3 never executes (flag only). Policy editable by admin within safe limits (Tier 3 types cannot be lowered). | P0 |
| FR-45 | Email recipients restricted to known contacts of that account (allowlist); internal CC allowed to org domain. | P0 |
| FR-46 | Cards expire after 7 days if not acted on (configurable). | P1 |
| FR-47 | Bulk approve for Tier 2 cards of the same type (manager+). | P2 |
| FR-48 | Assign/forward a card to another member. | P1 |

### 6.6 Execution, undo, log
| ID | Requirement | P |
|---|---|---|
| FR-50 | Executor runs only `approved` (or Tier 1 auto) cards, with idempotency key; retries with backoff. | P0 |
| FR-51 | Store pre-image before any CRM write; "Revert" restores it (if the field was not changed since). | P0 |
| FR-52 | Decision log: append-only, hash-chained; entries for finding created, card proposed, approved/edited/rejected, executed/failed, reverted, settings changed. | P0 |
| FR-53 | "Why" replay: open any log entry and see the evidence snapshot, rules fired, model + prompt version, output, approver, edits, API response. | P0 |
| FR-54 | Export decision log (CSV/JSON) for a date range (admin). | P1 |

### 6.7 Notifications
| ID | Requirement | P |
|---|---|---|
| FR-60 | Daily Slack DM digest at user's chosen time (default 09:00 local) with top items. | P1 |
| FR-61 | Daily email digest (optional). | P2 |
| FR-62 | In-app notifications (new high-severity finding, card assigned, execution failed, integration broken). | P0 |

### 6.8 Outcomes and learning (Phase 2)
| ID | Requirement | P |
|---|---|---|
| FR-70 | Track outcome per executed card: reply received, meeting booked, usage recovered, renewal won/lost. | P2 |
| FR-71 | Learn from edits and rejection reasons (per-user preferences in drafts, rule threshold suggestions). | P2 |
| FR-72 | Manager dashboard: approvals, time saved, ARR at risk vs saved. | P2 |
| FR-73 | Churn probability model (calibrated) shown only after validation. | P3 |

### 6.9 Platform admin (internal)
| ID | Requirement | P |
|---|---|---|
| FR-80 | List orgs, their integrations, last sync, error counts. | P1 |
| FR-81 | Job queue view, retry/kill job. | P1 |
| FR-82 | Model health: latency, JSON failure rate, citation failure rate. | P1 |
| FR-83 | Eval runs dashboard (golden dataset results per model/prompt version). | P1 |
| FR-84 | Feature flags per org. | P1 |

## 7. Key user flows

### 7.1 Onboarding (target: first explained finding in ≤ 15 minutes for a HubSpot org)
1. Sign up → create org (name, domain, timezone, currency).
2. Connect HubSpot → pick field mapping (renewal date, ARR, seats, plan, health field).
3. Connect own Google (Gmail + Calendar). Invite teammates who connect their own.
4. Usage: copy API key or upload CSV (optional; finding shows "usage unknown" if skipped).
5. Slack (optional).
6. Backfill starts → progress screen → first findings appear as they are ready.

### 7.2 Daily loop (Priya)
1. 09:00 Slack digest: "3 accounts need you today."
2. Opens Today: Acme (High risk, $84k ARR, renewal in 43 days), Globex (Expansion, seats 96/100), Initech (Medium).
3. Opens Acme finding: claims with chips — `[E1] renewal 2026-11-22 (HubSpot)`, `[E2] usage −38% over 4 weeks (Usage)`, `[E3] last meeting 21 days ago (Calendar)`, `[E4] 2 emails to champion unanswered for 9 days (Gmail)`. Unknowns: "Reason for usage drop not confirmed". Contradiction: "HubSpot health = Green".
4. Cards: email draft to champion (Tier 2), CRM task "Exec sponsor call" (Tier 1, already done), CRM field `health_status: Green → At Risk` (Tier 2), Slack note to manager (Tier 1).
5. Edits one line in the email, approves; approves CRM change. Draft appears in Gmail; HubSpot updated; log written.
6. Next day: if champion replies, Phase 2 outcome tracking marks it.

### 7.3 Approval from Slack
DM with card summary + evidence lines + buttons **Approve**, **Reject**, **Open**. Approve → card executes → message updates to "Approved by Priya · Executed ✓ · Revert". Reject → modal asks reason.

### 7.4 Revert
Log or card → **Revert** → system checks current CRM value equals the value we wrote → writes pre-image back → log entry `reverted`. If the field changed since, revert is refused with a message.

## 8. Roles and permissions

| Capability | owner | admin | manager | member | viewer |
|---|---|---|---|---|---|
| View accounts, findings, log | ✓ | ✓ | ✓ | ✓ (all accounts; "My accounts" filter default) | ✓ |
| Approve/reject cards on own accounts | ✓ | ✓ | ✓ | ✓ | – |
| Approve/reject cards on any account | ✓ | ✓ | ✓ | – | – |
| Edit card before approve | ✓ | ✓ | ✓ | ✓ (own) | – |
| Revert executed action | ✓ | ✓ | ✓ | ✓ (own, within 7 days) | – |
| Run agent now | ✓ | ✓ | ✓ | ✓ (own) | – |
| Connect own Google/Slack | ✓ | ✓ | ✓ | ✓ | ✓ |
| Connect org HubSpot / Slack workspace | ✓ | ✓ | – | – | – |
| Edit rules, field mapping, autonomy | ✓ | ✓ | ✓ (rules only) | – | – |
| Manage members | ✓ | ✓ | – | – | – |
| API keys, data export/delete | ✓ | ✓ | – | – | – |
| Delete org, transfer ownership | ✓ | – | – | – | – |

"Own account" = `accounts.owner_user_id = me` (from HubSpot owner mapping).

## 9. Non-functional requirements

| Area | Requirement |
|---|---|
| Security | Tokens encrypted at rest (Fernet/AES-GCM, key from env/KMS). TLS everywhere. RLS on every tenant table. LLM has no write tools. |
| Privacy | Self-hosted model; no customer data sent to third-party LLM APIs. Send snippets, not whole mailboxes, to the model. PII masked in app logs. Data deletion within 30 days of org deletion. Align with India DPDP Act 2023. |
| Gmail compliance | Gmail read/compose scopes are **restricted**: public launch needs Google OAuth verification + annual security assessment (CASA). Until then run in Testing mode / internal users (≤100 test users). See `research.md`. |
| Performance | Today page p95 < 800 ms. Approval click → executed p95 < 10 s (excluding provider outage). Nightly run for 500 accounts < 30 min on one GPU. |
| Reliability | Executor is idempotent; no duplicate emails/updates on retry. Jobs retried with backoff; dead-letter after 5 tries. |
| Accuracy | Citation validity 100% (enforced). Unsupported-claim rate < 5% on golden set. Rule precision ≥ 80% on golden set. |
| Auditability | Every state change in decision log; log is append-only (DB grants + hash chain). |
| Accessibility | WCAG 2.1 AA for web app. Severity never shown by color alone. |
| Observability | Sentry for errors, Langfuse traces for every model call, structured JSON logs with `org_id`, `run_id`, `card_id`. |
| Scale target (v1) | 50 orgs × 500 accounts, 10 users per org. |

## 10. Success metrics

| Metric | Target (pilot) |
|---|---|
| Daily active users / members | ≥ 60% |
| Cards approved (as-is or edited) / cards shown | ≥ 50% |
| Findings marked "not useful" | < 20% |
| Time from login to first action | < 2 min |
| Unsupported claims found by users | 0 reported per week |
| Phase 2: outcomes — reply rate on approved risk emails | baseline then +X% |

## 11. Constraints and assumptions

- Python 3.12 backend (FastAPI), Next.js frontend — chosen by founder.
- AI model: Qwen ~9B, self-hosted via vLLM. Exact version to be confirmed (closest verified: Qwen3.5-9B; fallback: Qwen3.8-27B). See `aiengineerhandover.md`.
- Team: small (1–3 developers). Prefer boring, proven tools; no microservices.
- First CRM HubSpot; first mail/calendar Google Workspace.

## 12. Open questions

1. Final product name and domain.
2. Exact Qwen version and GPU budget.
3. Send email directly vs Gmail draft only in v1? (Spec default: draft; "send" behind a feature flag.)
4. Pricing model (per seat vs per account vs % of ARR saved) — Phase 3.
5. Data residency (India vs US region) for first customers.
