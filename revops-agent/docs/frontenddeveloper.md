# frontenddeveloper.md — Frontend Developer Handover

> For the frontend developer (Next.js). Lists every **portal**, every **page**, each page's **features**, and every **field** shown or entered, with the API it comes from.
> API details: `backenddeveloper.md` §5 · Product rules: `spec.md` · Tasks: `task.md` (IDs `FE-xx`).

---

## 1. Stack

| Area | Choice |
|---|---|
| Framework | Next.js 15, App Router, React Server Components where useful, TypeScript strict |
| Styling | Tailwind CSS + shadcn/ui (Radix) + lucide-react icons |
| Data fetching | TanStack Query v5 (client) + server fetch in RSC for first paint |
| Forms | react-hook-form + zod |
| API types | `openapi-typescript` from FastAPI `/openapi.json` → `src/lib/api/schema.d.ts`; thin typed client (`openapi-fetch`) |
| Auth | Auth.js (NextAuth v5): Google provider + Email (magic link) provider |
| Charts | Recharts |
| Tables | TanStack Table |
| Rich text (email editor) | Plain `<textarea>` with markdown-lite in v1 (Tiptap later) |
| Live updates | Server-Sent Events from `/api/stream` (proxied) → invalidate queries |
| Dates | `date-fns` + `date-fns-tz` (show in user timezone) |
| Tests | Vitest + Testing Library (components), Playwright (E2E) |
| Lint | ESLint + Prettier |

## 2. How the frontend talks to the backend

```
Browser ──(cookie session)──▶ Next.js route handlers /api/* ──(Bearer service JWT, 5 min)──▶ FastAPI /api/v1/*
```
- Browser never calls FastAPI directly. `src/app/api/[...path]/route.ts` proxies requests, attaches the service JWT (signed with `API_JWT_SECRET`, claims: `sub`, `org_id`, `role`, `email`, `aud`, `exp`).
- Current org stored in session (`session.orgId`); org switcher updates it.
- SSE: `src/app/api/stream/route.ts` proxies `GET /api/v1/stream` (keep connection open; no buffering).
- OAuth connect buttons: call `POST /integrations/{provider}/connect` → `window.location = authorize_url`. Backend callback redirects back to `/settings/integrations?connected=<provider>` or `?error=<code>`.

## 3. Folder structure (`apps/web`)

```
src/
  app/
    (public)/login/page.tsx, signup/page.tsx, auth/check-email/page.tsx, auth/error/page.tsx, invite/[token]/page.tsx
    (onboarding)/onboarding/[step]/page.tsx
    (app)/layout.tsx                 # sidebar + topbar + SSE provider
    (app)/today/page.tsx
    (app)/inbox/page.tsx             # + parallel route @drawer for card detail
    (app)/accounts/page.tsx
    (app)/accounts/[id]/(tabs)/...   # overview, timeline, findings, actions, contacts, deals, usage
    (app)/findings/[id]/page.tsx
    (app)/log/page.tsx, log/[id]/page.tsx
    (app)/review/page.tsx            # entity match review
    (app)/runs/page.tsx, runs/[id]/page.tsx
    (app)/team/page.tsx              # P2
    (app)/outcomes/page.tsx          # P2
    (app)/settings/...               # see §7
    (admin)/admin/...                # platform admin portal
    api/[...path]/route.ts, api/stream/route.ts, api/auth/[...nextauth]/route.ts
  components/
    ui/ (shadcn)  layout/  evidence/  findings/  cards/  accounts/  charts/  settings/  common/
  lib/ api/ auth/ format/ permissions.ts sse.ts query-keys.ts
  styles/ tokens.css
```

## 4. Portals

| Portal | Path prefix | Users | Purpose |
|---|---|---|---|
| **A. Public & Auth** | `/login`, `/signup`, `/auth/*`, `/invite/*` | anyone | Sign in, sign up, accept invite |
| **B. Onboarding** | `/onboarding/*` | new org owner/admin; new member (short version) | Create org, connect systems, first sync |
| **C. Main App (Workspace)** | `/today`, `/inbox`, `/accounts`, `/findings`, `/log`, … | owner, admin, manager, member, viewer | Daily work |
| **D. Settings** | `/settings/*` | all (personal) + admin/manager (org) | Profile, integrations, rules, autonomy, members |
| **E. Platform Admin** | `/admin/*` | superadmin (internal) | Run the service |
| **F. Slack surface** | (in Slack) | members | Digest + approve/reject (built by backend; FE provides deep-link pages) |

### Global layout (portal C and D)
- **Sidebar** (collapsible; icons + labels): Today · Inbox (badge = pending cards assigned to me) · Accounts · Decision log · Review (manager+, badge = open entity reviews) · Runs (manager+) · Team (P2) · Outcomes (P2) · Settings.
- **Topbar**: org switcher (org name + avatar; list of memberships), global search (accounts by name/domain, `⌘K`), notifications bell (unread count), user menu (Profile, Notifications, Sign out).
- **Integration health banner**: if any org integration `needs_reauth`/`error` → yellow banner "HubSpot needs reconnecting — data since <time> may be missing. [Reconnect]" (admin sees button; others see "Ask an admin").
- **SSE provider** in layout: on `card.updated` invalidate `['cards', id]`, `['inbox']`, `['today']`; on `finding.updated` invalidate `['finding', id]`, `['today']`; on `run.updated` update run status chips; on `notification.created` bump bell.
- **Toasts** for action results.

### Permission helper
`lib/permissions.ts` exposes `can(role, action, {isOwnAccount})` matching `spec.md` §8. Hide buttons the user cannot use; never rely on hiding alone (backend enforces).

---

## 5. Shared components (build these first)

| Component | Props / fields | Notes |
|---|---|---|
| `SeverityBadge` | `severity: 'high'\|'medium'\|'low'` | Text + icon + color (never color alone): High = red + ▲▲, Medium = amber + ▲, Low = gray + • |
| `TypeBadge` | `type: 'risk'\|'expansion'` | Risk (shield-alert icon), Expansion (trending-up icon) |
| `TierBadge` | `tier: 1\|2\|3` | "Auto", "Needs approval", "Blocked" |
| `CardStatusBadge` | card status enum | proposed, pending_approval, approved, executing (spinner), executed ✓, failed ✕, rejected, reverted ↺, expired, blocked |
| `EvidenceChip` | `{key, kind, label, source, source_url, occurred_at}` | Shows `[E2] 📉 Usage −38%`; icon by source (HubSpot, Gmail, Calendar, Usage, Rule); click → popover with label, detail, date, "Open in <source>" link (new tab) |
| `ClaimList` | `claims[]`, `evidence[]` | Each claim text followed by its chips; hover a chip highlights the evidence row |
| `UnknownsList` | `string[]` | Gray box, icon "?" , title "Not confirmed" |
| `ContradictionsList` | `[{text, evidence_ids}]` | Amber box, icon "⇄", title "Signals that disagree" |
| `CrmDiff` | `[{object, field, label, before, after}]` | Table: Field · Before (strikethrough, red-ish bg) · After (green-ish bg); empty before shows "(empty)" |
| `EmailPreview` / `EmailEditor` | payload: to, cc, subject, body_text | Recipient chips limited to allowlist (dropdown of account contacts + internal); char counters |
| `MoneyText` | `amount, currency` | `$84,000` / `₹ 6,90,000` with org currency, compact on small widths |
| `RelativeDate` | `date` | "in 43 days", "21 days ago", tooltip with full date in user TZ |
| `AccountCell` | `{name, domain, owner, arr}` | Logo (favicon from domain via backend proxy or initials) + name + owner avatar |
| `EmptyState`, `ErrorState`, `LoadingSkeleton` | | Every list/page uses them |
| `ConfirmDialog` | | For revert, delete, disconnect |
| `UsageSparkline` / `UsageChart` | series | 12-week active users; seats purchased line |
| `PriorityScore` | 0–100 | Small bar + number, tooltip shows breakdown (value, urgency, severity, confidence) |

---

## 6. Portal A — Public & Auth

### A1. `/login` — Log in
**Features:** Continue with Google; email magic link; link to sign up; error display from `?error=`.
| Field | Type | Validation |
|---|---|---|
| Email | email input | required, valid email |
| Button "Continue with Google" | OAuth | — |
| Button "Email me a sign-in link" | submit | disabled while sending |
After login: if user has 0 orgs → `/onboarding/org`; if pending invite → `/invite/[token]`; else last org → `/today`.

### A2. `/signup` — Sign up
Same as login + text "By continuing you agree to Terms & Privacy". Fields: Full name (required, 2–80 chars), Work email (required; warn if free-mail domain: "Use your work email so we can detect internal vs customer emails").

### A3. `/auth/check-email` — "Check your email"
Shows email address, resend button (cooldown 60 s), "Use a different email" link.

### A4. `/auth/error` — Auth error
Messages per code: `link_expired`, `access_denied`, `account_disabled`. Button back to login.

### A5. `/invite/[token]` — Accept invite
Calls `POST /invites/accept`. Shows: Org name, Invited by (name), Role, Expiry. Buttons: Accept & continue (→ member onboarding), Decline. States: expired, already accepted, email mismatch ("This invite was sent to x@y. Sign in with that email.").

---

## 7. Portal B — Onboarding (`/onboarding/[step]`)

Stepper at top (steps with status: done / current / skipped / todo). Each step saves immediately; user can leave and resume (`GET /orgs/current/onboarding`). Owner/admin sees all steps; invited member sees only **B3 (Google)**, **B5-member (Slack link)**, **B7**.

### B1. `org` — Create your workspace
| Field | Type | Validation / default |
|---|---|---|
| Company name | text | required, 2–80 |
| Company website / primary domain | text | required, domain format, prefilled from email domain |
| Other internal domains | tag input | optional |
| Timezone | select (IANA) | default browser TZ |
| Currency | select | USD, INR, EUR, GBP… default by TZ |
| Team size | select | 1–5, 6–20, 21–50, 50+ (analytics only) |
API: `POST /orgs`.

### B2. `hubspot` — Connect HubSpot
- Card: HubSpot logo, what we read (companies, contacts, deals, notes, meetings, emails, tasks), what we may write **only after approval** (tasks, notes, selected fields). Link "Why these permissions?".
- Button **Connect HubSpot** → OAuth. After return: shows portal name/id, "Connected ✓", scopes list.
- Skip allowed? No (required in v1). If user is not HubSpot admin: copy text "Ask your HubSpot admin to connect".

### B3. `google` — Connect your Gmail & Calendar (per user)
- Explains: "We read emails and meetings **with your customers only**. Internal-only emails are ignored. Drafts we create stay in your Gmail Drafts until you send."
- Button **Connect Google** → OAuth. Shows connected email.
- Note while unverified: "This app is in testing — Google will show a warning screen" (feature flag).
- Skip allowed (findings show unknown "No email data from <user>").

### B4. `field-mapping` — Map your HubSpot fields
Dropdowns loaded from `GET /integrations/hubspot/properties?object=companies` (and deals).
| Field | Type | Notes |
|---|---|---|
| Renewal date property | select (date properties) | required; suggestions: `renewal_date`, `contract_end_date` |
| ARR property | select (number) | required unless MRR set |
| MRR property | select (number) | optional; ARR = MRR × 12 |
| Seats purchased property | select (number) | optional (needed for expansion X01) |
| Plan / tier property | select (enum/text) | optional |
| Health field to update | select (enum) | optional; if empty, CRM health updates are disabled |
| Health value mapping | 3 selects (Healthy / At risk / Critical → enum options) | shown if health field chosen |
| Account owner source | radio: HubSpot company owner (default) / Deal owner | |
Preview panel: 3 sample companies with mapped values (`renewal_date`, `ARR`, `seats`) so user can confirm. API: `PUT /field-mapping`.

### B5. `usage` — Product usage (optional)
Tabs:
- **API**: Generate key (name field) → shows key once with copy button + code sample (curl + Python + Node) for `POST /ingest/usage`. Fields in sample: `account_key`, `account_key_type`, `period_start`, `granularity`, `active_users`, `seats_used`, `logins`, `key_events`.
- **CSV upload**: drop zone (≤ 10 MB) → column mapping table: CSV column → target (`account_key`, `period_start`, `active_users`, `seats_used`, `logins`, `key_event:<name>`, ignore) + Account key type select → Validate → result (rows accepted, rejected with first 20 reasons) → Import.
- **Skip for now** (shows reminder later).

### B6. `slack` — Connect Slack (optional, admin)
Button Connect Slack (workspace). Then **Link members** table: Member name · Email · Slack user (auto-matched by email; select to fix). Default digest time (time picker, default 09:00).

### B7. `invite` — Invite your team (admin)
Rows: Email (required) · Role (select: admin, manager, member, viewer; default member) · [+ Add row]. Also "Copy invite link" (P2). API `POST /invites`.

### B8. `first-sync` — Getting your first insights
- Progress list per integration: HubSpot (companies x/y, contacts, deals, activities), Gmail per user (messages scanned), Calendar, Usage.
- Then "Analyzing accounts" progress (runs completed / total) via SSE `sync.updated` / `run.updated`.
- As soon as first finding exists: card "Your first insight is ready → Open Today". Typical message: "This usually takes 5–15 minutes. You can leave this page."

---

## 8. Portal C — Main App

### C1. `/today` — Today (priority list) ⭐ home page
**Purpose:** The short list of accounts that need attention today, ranked.
**API:** `GET /today?type=&owner=`; SSE updates.
**Layout:**
- Header: "Good morning, Priya" + date + summary line: "3 accounts need you · $214k ARR at risk · 5 actions waiting".
- Filters: Segmented control **All / Risk / Expansion**; Owner select **Me (default for member) / Everyone / <member>**; Severity multi-select; "Renewal within" select (30/60/90 days/any).
- List of **Finding rows** (ordered by `priority_score` desc):

| Field on row | Source | Format |
|---|---|---|
| Rank | index | 1, 2, 3… |
| Account name + logo | `account.name`, domain | link → `/accounts/[id]` |
| Type badge | `type` | Risk / Expansion |
| Severity badge | `severity` | |
| Title | `title` | one line, truncate |
| Top 2 reasons with chips | `top_reasons[]` | `Usage −38% [E2]` |
| ARR | `account.arr` | money |
| Renewal | `account.renewal_date`, `renewal_in_days` | "in 43 days" (red if ≤ 30) |
| Owner | `account.owner` | avatar |
| Pending actions | `pending_cards` | "2 actions" button |
| Flags | `unknowns_count`, `contradictions_count`, `is_new`, `changed_since_yesterday` | small icons: "New", "Changed", "?" , "⇄" |
| Priority score | `priority_score` | bar + tooltip breakdown |

**Row actions:** Open (→ `/findings/[id]`), Review actions (→ `/inbox?finding=<id>`), Snooze (menu: 1 day / 3 days / 1 week / custom date), Dismiss (dialog: reason select `not_relevant | already_handled | wrong_data | other` + note).
**Right panel (desktop ≥1280px):** "Waiting for you" mini-inbox: up to 5 pending cards with Approve/Reject quick buttons (Tier 2 only; email cards open drawer instead of quick approve).
**Empty state:** "Nothing urgent today 🎉 — 0 of 48 accounts need attention. Last checked 02:14." + link to Accounts.
**Stale data state:** if last nightly run > 30 h ago → warning "Insights may be out of date".
**Acceptance:** loads < 800 ms p95; keyboard nav (j/k to move, Enter to open).

### C2. `/findings/[id]` — Finding detail ("Why")
**Purpose:** Full explanation of one risk/expansion with evidence and actions.
**API:** `GET /findings/{id}`; actions via card endpoints; `POST /findings/{id}/feedback`.
**Sections:**
1. **Header:** Account name (link), Type, Severity, Status, Priority score, Confidence (as "Strong / Moderate / Weak evidence" — not a raw %; tooltip shows value), First seen, Last updated, Owner. Buttons: Run again (manual run), Snooze, Dismiss/Reopen, "Was this useful? 👍 👎".
2. **Summary:** `summary` paragraph.
3. **Why (claims):** `ClaimList` — every claim with chips. Hover chip → highlights evidence row in section 6.
4. **Not confirmed:** `UnknownsList`.
5. **Signals that disagree:** `ContradictionsList`.
6. **Evidence** table:
| Column | Field |
|---|---|
| Key | `evidence.key` (E1…) |
| Source | icon + `source` |
| What | `label` + `detail` (expand) |
| When | `occurred_at` |
| Open | `source_url` link |
7. **Rules that fired:** list of `rule_hits` with human text from rule key + metrics (e.g., "R01 Usage drop: 52 → 32 active users (−38%), threshold 30%"). Link "Edit rule" (manager).
8. **What changed** (P1): diff vs `previous_snapshot`: new claims (green +), removed (gray −), severity change.
9. **Suggested actions:** list of action cards (compact `ActionCardView`, see C4) with status; pending ones actionable inline.
10. **History:** timeline of log entries for this finding (created, updated, cards decided) → link to `/log/[id]`.
11. **Model info (collapsed, manager+):** model, prompt_version, agent_run_id link.
**States:** `needs_review` → banner "We could not fully verify this explanation. Showing rule results only." ; `dismissed` → banner with reason + Reopen.

### C3. `/inbox` — Approval inbox
**Purpose:** All action cards waiting for decision.
**API:** `GET /action-cards?status=pending_approval&assignee=me`.
**Layout:** Left list + right detail drawer (route `/inbox/[cardId]` as parallel/intercepting route so the URL is shareable).
**Filters:** Tabs **Waiting for me / All pending (manager) / Approved / Executed / Failed / Rejected**; Type multi-select (Email, CRM task, CRM update, CRM note, Slack, Meeting); Account search; Sort (priority / oldest / expiring soon).
**List row fields:**
| Field | Source |
|---|---|
| Type icon + title | `type`, `title` |
| Account | `account.name` |
| Finding severity | finding.severity |
| Tier badge | `tier` |
| Created | `created_at` relative |
| Expires | `expires_at` ("expires in 2 days") |
| Assignee | `assignee` avatar |
| Status | `status` |
**Bulk (P2, manager):** select multiple Tier 2 non-email cards → Approve selected.
**Empty:** "No actions waiting. Nice."

### C4. Card detail drawer (`/inbox/[cardId]`, also used inside finding page)
**Common fields (all types):**
| Field | Source | Editable |
|---|---|---|
| Title | `title` | no |
| Account + finding link | `account`, `finding_id` | no |
| Why this action | `rationale` + evidence chips (`evidence_keys`) | no |
| Tier | `tier` with explanation text | no |
| Status | `status` | no |
| Assignee | `assignee_user_id` | yes (Assign dialog) |
| Expires | `expires_at` | no |
| Decision info | `decided_by`, `decided_at`, `decision_channel` | no |
| Execution info | `executed_at`, `external_ref` (link "Open draft in Gmail", "Open task in HubSpot"), `error` | no |
**Buttons:** Approve (primary) · Save edits · Reject (dialog: reason `wrong_action | wrong_content | not_now | already_done | other` + note) · Assign · Revert (if executed & revertable) · Retry (failed, manager).
Approve with unsaved edits → sends `edited_payload` in approve call. After approve: optimistic status "Approved · executing…", then SSE → executed ✓ / failed ✕ with error.

**Type-specific body:**

**a) `email_draft`**
| Field | Type | Rules |
|---|---|---|
| To | recipient chips + dropdown | only account contacts (name, title, email); at least 1 |
| CC | chips | account contacts + internal domain addresses |
| Subject | text | required, ≤ 200 |
| Body | textarea (auto-grow) | required, ≤ 5,000; shows word count |
| Reply in thread | toggle + thread subject | if `reply_to_thread_id` present |
| Mode | read-only text "Will be saved as a draft in your Gmail" (or "Will be sent" if feature flag) | |
| Evidence used | chips | |
Warning banner if the email mentions price/discount words → "Pricing language detected — pricing changes are blocked; edit or confirm this is not an offer." (FE hint only; backend policy is the real guard.)

**b) `crm_task`**
Fields: Task title (text ≤ 200), Notes (textarea ≤ 2,000), Due date (date picker, default +2 business days), Owner (select of members with CRM owner mapping), Priority (Low/Medium/High), Associated records (read-only chips: Company, Deal).

**c) `crm_field_update`**
`CrmDiff` table: Object (Company/Deal) · Record name · Field label · Before · After. "After" editable only within allowed enum values (select). Info line: "We will check the current value before writing. If it changed, we stop." Revert availability note.

**d) `crm_note`**
Fields: Note body (textarea ≤ 5,000), Associated records (chips).

**e) `slack_internal`**
Fields: Destination (DM to member / channel — select), Message (textarea ≤ 3,000), preview of how it looks in Slack.

**f) `meeting_request`** (P1)
Fields: Title, Attendees (account contacts + internal), Duration (15/30/45/60), Proposed slots (up to 3 datetime pickers, user TZ), Description.

**Tier 3 (blocked) card:** read-only, red banner "Blocked by policy: pricing/contract changes must be done manually." Button "Mark as handled".

### C5. `/accounts` — Accounts list
**API:** `GET /accounts`.
**Filters:** Search (name/domain), Owner, Risk level (High/Medium/Low/None), Has expansion (yes/no), Renewal within (30/60/90/180), Status (active/churned/archived), Data gaps (no usage / no email).
**Columns (sortable where marked ↕):**
| Column | Field |
|---|---|
| Account ↕ | name, domain, logo |
| Owner | owner |
| ARR ↕ | `arr` |
| Plan | `plan_name` |
| Renewal ↕ | `renewal_date` (+ days) |
| Risk | `risk_level` badge |
| Expansion | dot if open expansion finding |
| Usage trend | 8-week sparkline + % change |
| Seats | `seats_used / seats_purchased` |
| Last activity ↕ | `last_activity_at` |
| CRM health | `crm_health` |
| Priority ↕ | `priority_score` |
Row click → `/accounts/[id]`. Export CSV (manager+, P2). Pagination: infinite scroll with cursor.

### C6. `/accounts/[id]` — Account detail
**Header (all tabs):** Logo, Name, Domains (chips), Owner, ARR, Plan, Seats used/purchased, Renewal date (+days), Lifecycle stage, CRM health, our Risk level, "Open in HubSpot" link, Last analyzed (`last_run_at`) + **Run analysis now** button (shows run status via SSE).
**Tabs:**

**C6.1 Overview**
- Open findings cards (risk + expansion) with severity, title, top reasons → link.
- Key metrics tiles: Days since last meeting · Days since last customer reply · Active users (current vs 4-week baseline, %) · Seat utilization % · Open deals (count, amount) · Next renewal.
- Usage chart (12 weeks: active users line, seats purchased line).
- Stakeholders mini-list: champion, decision maker (from contact `role_tags`), status (active/left).
- Pending actions count → inbox filtered.

**C6.2 Timeline**
- Filters: type chips (Emails, Meetings, Notes, Deal changes, Usage, Tasks, Signals), date range, search text.
- Each item: icon by type · title · summary · participants (avatars/emails) · date · source link · **signals** extracted (badges e.g. "Negative sentiment", "Competitor: Gainsight", with quote on hover) · "Used as evidence in: <finding>" tag.
- Infinite scroll, newest first. Data: `GET /accounts/{id}/timeline`.

**C6.3 Findings** — table of all findings (open + closed): Type, Severity, Title, Status, First seen, Last updated, Outcome (P2).

**C6.4 Actions** — all cards for the account: Type, Title, Status, Decided by, Executed at, Revert button.

**C6.5 Contacts** — Name, Title, Email, Role tags (editable chips P1: champion/decision maker/…), Active/Left, Last inbound, Last outbound, HubSpot link. Note: role tags edits write locally (not to CRM) in v1.

**C6.6 Deals** — Name, Type (renewal/expansion/new), Stage, Amount, Close date, Next step, Owner, HubSpot link.

**C6.7 Usage** — granularity toggle (day/week), metric select (active users, logins, seats used, each key event), table view toggle, last ingest time, "No usage data connected" empty state with link to settings.

### C7. `/log` — Decision log
**API:** `GET /log`.
**Filters:** Date range, Account, Event type (multi), Actor (user/agent/system or specific member).
**Columns:** Time · Actor (avatar or "Agent"/"System") · Event (human text, e.g., "Priya approved 'Email to champion'") · Account · Entity link · Channel (web/slack/auto).
**Admin extras:** "Verify integrity" button (`GET /log/verify`) → result badge; "Export" dialog (date range, CSV/JSON).

### C8. `/log/[id]` — Why replay
Shows one entry and its chain:
- Step timeline: Evidence snapshot → Rules fired (with metrics) → AI explanation (claims + chips; model + prompt version) → Proposed card (original payload) → Human decision (who, when, channel, **edit diff** original vs edited, rejection reason) → Execution (request summary, response, external link) → Revert (if any) → Outcome (P2).
- Hash + prev hash (monospace, collapsible) for audit.

### C9. `/review` — Entity match review (manager+)
List of `entity_match_reviews`: Event (email subject/meeting title, date, participants) · Reason ("domain shared by 2 accounts", "unknown domain") · Candidate accounts (radio list) · Actions: Assign to selected, Search other account, Ignore. Bulk ignore by domain (P2).

### C10. `/runs` and `/runs/[id]` — Agent runs (manager+)
List: Account · Trigger · Status · Started · Duration · Rule hits · LLM calls · Tokens · Error.
Detail: node-by-node steps with timing (load_evidence, extract_signals, run_rules, explain, validate, propose, approval, execute, record), validation failures (claims dropped), link to Langfuse trace (if configured), Retry button.

### C11. Notifications panel (bell)
Items: icon by kind, title, body, time, link; "Mark all read". Kinds: new high finding, card assigned to you, execution failed, integration error, digest ready.

### C12. `/team` (P2, manager+)
Per member: accounts owned, open findings (by severity), pending cards, approvals this week, avg time to decision, ARR at risk. Click member → Today filtered by owner.

### C13. `/outcomes` (P2)
Executed actions with outcome: Account · Action · Executed at · Outcome (reply received / meeting booked / usage recovered / renewal won/lost / no change) · Days to outcome. Summary tiles: reply rate, recovered ARR, renewals saved.

---

## 9. Portal D — Settings (`/settings/*`)

Left sub-nav grouped: **Personal** (Profile, My connections, Notifications) · **Workspace** (General, Members, Integrations, Field mapping, Rules, Autonomy, API keys, Data & privacy, Billing P3).

| Page | Who | Fields / features | API |
|---|---|---|---|
| **D1 `/settings/profile`** | all | Name, Email (read-only), Avatar (from Google), Timezone (select), Language (EN only v1) | `PATCH /me` |
| **D2 `/settings/connections`** | all | My Google: status, email, scopes, last sync, Reconnect, Disconnect (confirm). My Slack link: Slack user, re-link | `GET /integrations`, connect/delete |
| **D3 `/settings/notifications`** | all | Daily digest: channel (Slack DM / Email / Off), time (time picker), days (Mon–Fri / every day); Instant alerts: high-severity finding (on/off), card assigned (on/off), execution failed (on/off) | `PATCH /me` |
| **D4 `/settings/general`** | admin | Org name, Primary domain, Internal domains (tags), Timezone, Currency, Nightly analysis hour (0–23), Backfill days (30/90/180), Card expiry days (3/7/14) | `PATCH /orgs/current` |
| **D5 `/settings/members`** | admin | Table: Name, Email, Role (select), Status, HubSpot owner (select from owners), Slack user, Google connected ✓/✕, Last active; Invite button (email + role); Pending invites (resend, revoke); Remove member (confirm) | members, invites |
| **D6 `/settings/integrations`** | admin (org), all (view) | Cards for HubSpot, Google (per-user count connected), Slack, Usage API, CSV. Each: status badge, account label, last sync, last error, "Sync now", "View sync history" (table: started, duration, status, fetched, new events, error), Disconnect | integrations, sync-runs |
| **D7 `/settings/field-mapping`** | admin | Same form as B4 + "Writable CRM fields" checklist (which fields agent may propose to change) | field-mapping |
| **D8 `/settings/rules`** | manager+ | Table of rules: Key, Name, Category, Type (risk/expansion), Enabled toggle, Params (inline form per rule, e.g. "Drop threshold %" number 10–90, "Window weeks" 2–8), "Preview" (shows how many accounts would fire now), Reset to default. Changes logged | rules |
| **D9 `/settings/autonomy`** | admin | Table: Action type · Tier (select 1/2/3) · Locked (lock icon for tier-3 defaults, cannot lower) · Conditions (e.g., email max recipients). Explanation panel of tiers | autonomy |
| **D10 `/settings/api-keys`** | admin | List: Name, Prefix, Scopes, Created by, Last used, Revoke; Create (name) → show once | api-keys |
| **D11 `/settings/data`** | admin/owner | Export decision log; Export all data (P2); Delete organization (owner, type org name to confirm); Data retention info | log export, org delete |

Rule params form schema comes from backend (`GET /rules` returns `params_schema` JSON Schema) → render with a generic schema form component.

---

## 10. Portal E — Platform Admin (`/admin/*`, superadmin only)

Separate layout (dark header "Internal"). Not linked from customer UI.
| Page | Features / fields |
|---|---|
| **E1 `/admin/orgs`** | Table: Org, Plan, Members, Accounts, Integrations (status icons), Last nightly run, Error count 24 h, Created. Search. |
| **E2 `/admin/orgs/[id]`** | Overview, integrations with errors, recent runs, failed jobs, feature flags for this org, Suspend/Unsuspend (confirm). No customer email content shown (privacy). |
| **E3 `/admin/jobs`** | Queues with depth (sync/agent/executor/notify), failed jobs table (task, org, error, failed at) with Retry / Discard. |
| **E4 `/admin/llm`** | Model name/version, uptime, p50/p95 latency, tokens/min, JSON failure rate, citation failure rate (24 h, 7 d charts). |
| **E5 `/admin/evals`** | Eval runs: date, model, prompt versions, metrics (citation validity, unsupported claim rate, rule precision/recall, extraction F1, JSON validity, latency) vs thresholds (pass/fail), Run eval button. |
| **E6 `/admin/flags`** | Feature flags: key, description, default, per-org overrides (e.g., `email_send`, `meeting_request`, `slack_approvals`). |

---

## 11. Portal F — Slack surface (built by backend; FE responsibilities)

- Deep links in Slack open `WEB_URL/inbox/<cardId>`, `/findings/<id>`, `/accounts/<id>` — these pages must work as direct entry (auth redirect back after login).
- Daily digest content (for reference): header "3 accounts need you today", per item: severity, account, title, ARR, renewal, "Open" button; footer "5 actions waiting → Inbox".

---

## 12. UX rules

1. **Evidence everywhere:** any AI sentence shown in UI must have chips. If a sentence has no chip, do not render it (defensive check).
2. **Severity never by color alone:** text label + icon.
3. **Confidence wording:** Strong (≥0.75), Moderate (0.5–0.75), Weak (<0.5). No fake precise percentages.
4. **Nothing external happens without a clear button** labeled with the effect: "Approve & save draft to Gmail", "Approve & update HubSpot".
5. **Optimistic but honest:** show "executing…" until SSE confirms; on failure show error + Retry.
6. **Empty, loading, error states** for every list and panel (skeletons, not spinners, for lists).
7. **Keyboard:** `⌘K` search, `j/k` list nav, `a` approve (with confirm for email), `r` reject, `Esc` close drawer.
8. **Responsive:** Today, Inbox, Finding detail, Card drawer must work on mobile (approvals on the go). Settings can be desktop-first.
9. **Dates** in user timezone; tooltips with absolute date.
10. **Accessibility:** WCAG 2.1 AA, focus rings, ARIA on chips/popovers, contrast ≥ 4.5:1.
11. **Copy tone:** simple, specific, no jargon ("Usage down 38% in 4 weeks", not "Adoption anomaly detected").
12. **Theme:** light + dark via CSS variables in `styles/tokens.css` (shadcn tokens). Semantic tokens: `--risk-high`, `--risk-medium`, `--risk-low`, `--expansion`, `--tier-auto`, `--tier-approval`, `--tier-blocked`.

## 13. Query keys & caching

| Key | Endpoint | staleTime |
|---|---|---|
| `['me']` | `/me` | 5 min |
| `['today', filters]` | `/today` | 30 s + SSE invalidation |
| `['inbox', filters]` | `/action-cards` | 15 s + SSE |
| `['card', id]` | `/action-cards/{id}` | 0 + SSE |
| `['finding', id]` | `/findings/{id}` | 30 s + SSE |
| `['accounts', filters]` | `/accounts` | 60 s |
| `['account', id]` / `['timeline', id, filters]` / `['usage', id]` | | 60 s |
| `['log', filters]` | `/log` | 30 s |
| `['integrations']` | `/integrations` | 30 s + SSE `sync.updated` |

Mutations: approve/reject/edit/assign/revert → optimistic update of `['card', id]` and remove from `['inbox']`, rollback on error.

## 14. Testing

- **Component tests:** EvidenceChip, ClaimList (no-chip sentence hidden), CrmDiff, EmailEditor (allowlist), SeverityBadge (text present), permission helper.
- **E2E (Playwright)** against seeded backend:
  1. Login → Today shows Acme at rank 1 with High risk.
  2. Open Acme finding → 4+ claims each with chips → open chip popover.
  3. Inbox → edit email subject → Approve → status becomes Executed (fake Gmail) → log shows edit diff.
  4. Approve CRM update → Revert → status Reverted.
  5. Member cannot see Settings › Autonomy edit controls.
  6. Onboarding happy path with mocked OAuth.
- Visual check on 375 px (mobile) for Today, Inbox, Card drawer.

## 15. Definition of done (frontend task)
- Uses generated API types (no hand-written response types).
- Has loading/empty/error states, keyboard access, mobile check where required.
- Permission-gated UI matches `spec.md` §8.
- Component test or E2E step added.
- No console errors; Lighthouse accessibility ≥ 95 on Today, Inbox, Finding.
