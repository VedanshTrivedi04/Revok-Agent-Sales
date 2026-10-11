# Testing guide: run the platform locally and check it portal by portal

For: the developer testing by hand. Everything runs on your machine against a throw-away local
database. **Never point this at the Neon database** (`apps/api/.env` does; the commands below
override it).

## 0. Start the stack (3 PowerShell windows)

Docker Desktop must be running with the `infra-postgres-1` (5433) and `infra-redis-1` (6379)
containers up (`docker ps`). If not: `docker compose -f revops-agent/infra/docker-compose.yml up -d`.

**Window 1: API** (also gives you the "emails": links are printed in this window)

```powershell
cd D:\CDGI2026\revops-agent\apps\api
$env:APP_ENV="local"; $env:MOCK_API="false"; $env:RATE_LIMIT_ENABLED="false"
$env:API_JWT_SECRET="e2e-local-secret-e2e-local-secret-0123456789"
$env:DATABASE_URL="postgresql+asyncpg://app:app@localhost:5433/revops"
$env:DATABASE_ADMIN_URL="postgresql+asyncpg://admin:admin@localhost:5433/revops"
$env:DATABASE_MIGRATOR_URL="postgresql+psycopg://owner:owner@localhost:5433/revops"
$env:REDIS_URL="redis://localhost:6379/0"
$env:WEB_URL="http://localhost:3100"; $env:PUBLIC_API_URL="http://localhost:8100"
uv run alembic upgrade head
uv run python scripts/e2e_reset.py        # fresh demo data (14 customers); safe, local only
uv run uvicorn app.main:app --port 8100
```

**Window 2: Web**

```powershell
cd D:\CDGI2026\frontend
$env:NEXT_PUBLIC_API_BASE="http://localhost:8100"; $env:NEXT_PUBLIC_APP_URL="http://localhost:3100"
$env:API_JWT_SECRET="e2e-local-secret-e2e-local-secret-0123456789"
$env:SESSION_SECRET="e2e-local-secret-e2e-local-secret-0123456789"
npx next build --webpack
npx next start -p 3100
```

Open **http://localhost:3100**. To get clean data again at any time, run the `e2e_reset.py` line
in Window 1's shell (stop the API first, or just run it from a third window with the same variables).

**Logins** (password for all: `Demo@12345678`)

| Who | Email | Portal |
|---|---|---|
| Owner | olivia@demo-saas.example.com | http://localhost:3100/login |
| Admin | adam@demo-saas.example.com | /login |
| Manager | maya@demo-saas.example.com | /login |
| Member (owns Acme) | priya@demo-saas.example.com | /login |
| Viewer | victor@demo-saas.example.com | /login |
| Platform operator | sam@platform.revops.example.com | /admin/login only |

**What cannot work locally** (needs real accounts, see `go-live.md`): connecting HubSpot, Google or
Slack (the Connect buttons will report an error, which is correct without client ids), and
actually carrying out an approved action (no worker is running, so an approved card stays
"approved"). Everything else below works.

## 1. Portal A: sign-in and account pages (signed out)

1. `/login` with a wrong password: "Incorrect email or password". Five wrong attempts: locked for 15 minutes (use a throw-away email, not Priya).
2. `/login` as Priya: lands on `/today`. Sign out from the top bar.
3. `/login` as **sam@platform...**: must be rejected (platform users only use `/admin/login`).
4. `/signup`: create `you+test@example.com` with a 10+ character password. You land on `/onboarding/org` (no workspace yet). Create a workspace named anything; you become its Owner and land on the HubSpot step.
5. `/invite/not-a-real-token`: a clear "invalid" message, not a blank page.

## 2. Portal E: Platform Admin (do this early, it creates a client for step 3)

Sign in at `/admin/login` as sam.

1. **Orgs** (`/admin/orgs`): Demo SaaS and Other Co (suspended) listed with counts only (no customer content).
2. Click **Onboard client**. Fill: name "Test Client", owner name + email `owner1@testclient.example.com`. Tick **Generate a temporary password** and untick the email option, submit.
   The temporary password is shown **once**: copy it. (If you tick the email option instead, the set-password link is printed in Window 1.)
3. Open the new org (`/admin/orgs/<id>`): overview and integration status; try **Suspend** then **Unsuspend**. While suspended, a customer of that org gets a "workspace suspended" notice.
4. **Analytics** (`/admin/analytics`): ten headline numbers (orgs, users, accounts, waiting for approval, approval rate, median time to decide, carried-out rate, connections, failed jobs), then charts: Growth, Detection activity, Decisions on action cards, Execution results, Approval funnel, Open findings, Integration health, Sync runs, Most fired rules, and a table of the most active organizations. Check: the **Period** selector refetches; hover (or use the left/right arrow keys on a focused chart) shows a tooltip; **Table** shows the same numbers; no account names, emails or finding titles appear anywhere. A customer Owner opening this URL gets the 403 page.
5. **Jobs, LLM health, Evals, Flags** (`/admin/jobs`, `/llm`, `/evals`, `/flags`): pages load; flags show `email_send`, `meeting_request`, `slack_approvals`, `prompt_variant`. LLM health and Evals are placeholders until the AI service is connected.
6. Visit `/today` while signed in as sam: you get the 403 "platform accounts" page, never customer data.

## 3. Portal A again: first login of the new client Owner

1. Sign out. Go to `/login`, use `owner1@testclient.example.com` + the temporary password.
2. You are sent to `/change-password` and cannot reach anything else (try typing `/today`).
3. Choose a new password. You land on `/today` (empty: nothing is connected).
4. Sign out and sign in again with the new password. The temporary one must now fail.

## 4. Portal B: onboarding (as the new Owner, or Olivia)

Go to `/onboarding/hubspot` and walk the stepper in order. Without real apps you check the behaviour, not the data.

| Step | Page | What to check |
|---|---|---|
| 1 | `/onboarding/org` | Name, domain, currency. Creates the workspace, then goes to HubSpot. |
| 2 | `/onboarding/hubspot` | Connect button starts OAuth (errors without a HubSpot app: expected). Continue is disabled until connected. A Member opening this gets a 403. |
| 3 | `/onboarding/field-mapping` | Loads; without HubSpot the dropdowns fall back to text inputs. Save is blocked until renewal date + ARR/MRR are set. |
| 4 | `/onboarding/usage` | **API key** tab: generate a key, copy it (shown once), see the curl example. **CSV** tab: upload a CSV with columns like `domain,week_start,active_users`; confirm the column mapping; Import; watch the result (accepted / rejected rows). "Skip" works. |
| 5 | `/onboarding/slack` | Admin: Add to Slack (errors without a Slack app). A Member sees a read-only explanation instead. |
| 6 | `/onboarding/invite` | Owner's role list is Admin, Manager, Member, Viewer. Admin's is Manager, Member, Viewer. Never Owner. Send an invite: the link (`/invite/<token>`) is printed in Window 1. |
| 7 | `/onboarding/google` | Gmail and Calendar rows with Connect (errors without a Google app: expected). Skip works. |
| 8 | `/onboarding/first-sync` | Per-integration progress, and "Open Today" turns green when a first finding exists. |

**Invite round trip:** open the printed `/invite/<token>` link in a private window. You should see
the workspace name, role and inviter before signing in. Sign up with the invited email, accept,
and you are sent to the Google step. Opening the same link again says it was already used.

## 5. Work portal (as Priya, then repeat key pages as other roles)

Sign in as **Priya** (Member).

1. **Today** (`/today`): Acme Corp is **#1**, High risk, with evidence chips. Filters, "View finding", Snooze, Dismiss. The list defaults to *your* accounts; a Manager sees everyone.
2. **Finding** (open Acme's): confirm the product's promise page by page:
   - header: severity, "Strong/Moderate/Weak evidence" (not a raw %), priority, owner, renewal;
   - **Why**: every sentence has `[E1]`-style chips; click one for the source popover;
   - **Not confirmed** and **Signals that disagree** boxes;
   - **Evidence** table, **Rules that fired** (with numbers), **Suggested actions**, **History**;
   - Snooze (pick days), Dismiss (pick a reason), then **Reopen**. "Was this useful?" Yes/No.
3. **Inbox / card** (open the email draft): see To, Subject, Message, and the line "saved as a draft in your Gmail, nothing is sent".
   Click **Edit**, change the subject, **Save edits**, then **Approve and save draft** and confirm in the dialog.
   Without a worker the status stays "approved". Try **Reject** on another card (choose a reason). Open a CRM field-update card: it shows Before (struck) and After.
   A Tier 3 card shows "Blocked by policy" and cannot be approved.
4. **Decision log** (`/log`): your approval is at the top. Click **Why Replay**: you see the evidence at the time, the rule results, **"What was edited before approval"** (original vs your edit), and the execution. As Owner/Admin: **Verify integrity** (real check) and **Export log** (downloads a CSV).
5. **Accounts** (`/accounts`): 14 customers; open Wayne Logistics or Tyrell Corp (the other at-risk stories) and Dunder Mifflin (nothing to do). Tabs: Overview, Timeline, Findings, Actions, Contacts, Deals, Usage. **Run analysis now** queues a run.
6. **Role checks** (sign out, sign in as each):
   - **Victor (Viewer):** "Read-only" shown; no Snooze/Dismiss/Approve anywhere.
   - **Priya:** `/review`, `/rules`, `/control/members` show "You don't have access".
   - **Maya (Manager):** sees everyone's items; `/review` (entity matches: Ignore or pick an account), `/runs` (runs list, open one for step timings, **Retry** on a failed one), `/rules` (Tune a rule, Preview, Save, "Re-run now"). `/control/overview` shows "You don't have access" and the sidebar has no Control switch.
   - **Olivia/Adam (Owner/Admin):** land on `/control/overview`; the Control / Work switch at the top of the sidebar moves between the two portals.
7. **Notifications** (bell, top bar): list loads; "Mark all read".

## 6. Control portal (as Olivia or Adam)

Signing in as Owner or Admin lands on `/control/overview`. Every chart has a **Table** button that
shows the same numbers as rows, a tooltip on hover or keyboard focus, and an honest empty state
when the workspace has no data for it. The **Period** and **Account owner** filters at the top
apply to every chart on the page and stay set while you move between analytics pages.

| Page | Check |
|---|---|
| Overview `/control/overview` | Eight tiles (revenue, revenue at risk, renewals, open findings, waiting for approval...), findings per week, decisions per week, accounts by risk level. Acme's ARR is inside "Revenue at risk". |
| Pipeline & renewals | Open pipeline by stage, deal types, 12-month renewal calendar split into healthy and at risk. |
| Risk map | Revenue by risk level, heatmap of accounts x signal category (click an account name), revenue vs priority dots (click a dot to open the account). |
| Findings | New findings per week by severity; by rule, category, status; dismissal reasons. |
| Team performance | Revenue owned, decisions made and current backlog per person; accounts without an owner. |
| Automation | Approval rate, edit rate, time to decide; by action type, tier, channel; rejection reasons. Approve a card in the Work portal, come back: the numbers move. |
| Data health | Connections, field coverage meters, sync runs per day, detection runs by outcome. |
| Clients `/control/clients` | Every account with owner, revenue, renewal, risk; search, filter by risk/owner, sort; change a client's status; "Account 360" opens the account. Owners are not edited here: they follow HubSpot, mapped in Members. |
| Members, Workspace, Integrations, Field mapping, Autonomy, API keys, Data & privacy | The former workspace settings, same behaviour as below, now under `/control/*`. |

Change the period to "Last 30 days" and pick an owner: the tiles and charts update together.

### Workspace setup pages (Control) and personal settings (Work)

| Page | Check |
|---|---|
| Profile `/settings/profile` | Name, timezone, role shown read-only. |
| My connections `/settings/connections` | Google status; Connect/Disconnect (Connect errors without an app). Slack shows "workspace connected" only once an admin linked you. |
| Notifications | Change digest hour/days and the three instant alerts, Save, reload: values stay. |
| General `/control/workspace` | Change name, domains, timezone, currency, nightly hour, card expiry; Save. A Manager cannot open it. |
| Members | List with roles; change a role; remove a member; invite (roles offered follow the hierarchy); last Owner cannot be removed or demoted. |
| Integrations | Cards for HubSpot, Google, Slack, Usage with real status; Connect (errors without apps); "Sync history" expands. |
| Field mapping | Same form as onboarding; preview table after saving. |
| Rules `/rules` (Work portal, Manager and up) | Toggle, Tune, **Preview** ("would fire on N accounts"), Reset to default, then "Re-run now". |
| Autonomy | Tiers: Auto / Needs approval / Blocked. Locked rows (pricing, contract) cannot be lowered. Note says existing cards keep their old tier. |
| API keys | Create (shown once), Revoke. |
| Data & privacy | **Export decision log** (downloads a file). Owner only: Delete workspace (type the name to confirm; do this only on a test workspace). |

## 7. Quick sanity pass after any change

```powershell
cd D:\CDGI2026\frontend
npm run typecheck; npm run lint; npm test
npm run test:e2e        # real browser, resets local data, ~2 minutes
cd ..\revops-agent\apps\api
uv run pytest -q        # uses disposable containers, never your .env database
```

## If something looks wrong

- Blank page or endless redirect: sign out (clear site cookies for localhost:3100) and retry.
- "Backend unavailable": Window 1 is not running or the web app was started without `NEXT_PUBLIC_API_BASE`.
- Data looks stale or half-edited: re-run `scripts/e2e_reset.py`.
- Note any page that behaves differently from this guide; pages I have not clicked through in a
  browser myself are Team, Outcomes, Accounts list filters and the Admin org detail actions.
