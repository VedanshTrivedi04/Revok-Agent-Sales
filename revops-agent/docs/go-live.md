# Go-live checklist: the parts that need real accounts

Everything in the codebase that can be built and tested without third-party accounts is built and
tested (backend suite, browser E2E on a real stack, CI). This page lists what is **left to do by a
person with the right account**, in the order that unblocks the most, with the exact settings the
code expects. Nothing here is done yet.

## 0. Do these first (security and housekeeping)

1. **Rotate the Neon database passwords.** They were printed in a session transcript. Create new
   credentials in Neon, update `apps/api/.env` (`DATABASE_URL`, `DATABASE_ADMIN_URL`,
   `DATABASE_MIGRATOR_URL`) and your hosting secrets.
2. **Migrate Neon to head** (`0005` passwords, `0006` set-password links and forced change):
   ```bash
   cd revops-agent/apps/api
   uv run alembic upgrade head
   ```
   Run it only after step 1, and read the output: it must end at `0006`.
3. **Clean up stray Neon users** (for example `you@company.com`), then create the real platform
   operator: `uv run python scripts/set_password.py you@yourcompany.com --superadmin`.
4. **Never run `TEST_INFRA=compose` pytest** with `apps/api/.env` pointing at Neon. The default
   test mode uses disposable containers. `scripts/e2e_reset.py` refuses any non-local database.
5. Generate production secrets (32+ characters, unique): `API_JWT_SECRET` (same value in the API and
   the web app), `SESSION_SECRET`, `INTERNAL_API_KEY`, and `TOKEN_ENC_KEYS`
   (`k1:<base64 of 32 random bytes>`). The API refuses to start outside local without them.

## 1. HubSpot (blocks the whole data loop)

Create a **public app** at developers.hubspot.com and a **test portal** with ~10 demo companies.

| Setting | Value |
|---|---|
| Redirect URL | `{PUBLIC_API_URL}/api/v1/oauth/hubspot/callback` |
| Scopes | `crm.objects.contacts.read/write`, `crm.objects.companies.read/write`, `crm.objects.deals.read/write`, `crm.objects.owners.read`, `crm.schemas.companies.read`, `crm.schemas.deals.read`, `crm.schemas.contacts.read` |
| Env | `HUBSPOT_CLIENT_ID`, `HUBSPOT_CLIENT_SECRET` |

In the test portal create custom company properties for renewal date (date), ARR (number), seats
(number), plan (enumeration) and health (enumeration with Green / At Risk / Red). Then follow
onboarding step 2 and 3 in the web app. Acceptance: companies and contacts appear in Accounts, and
`scripts/reconcile_hubspot.py` passes against the portal.

## 2. Google (Gmail and Calendar) and the verification clock

Create a Google Cloud project, configure the OAuth consent screen, and add an OAuth client (web).

| Setting | Value |
|---|---|
| Redirect URIs | `{PUBLIC_API_URL}/api/v1/oauth/gmail/callback` and `{PUBLIC_API_URL}/api/v1/oauth/gcal/callback` |
| Scopes | `gmail.readonly`, `gmail.compose`, `calendar.readonly`, `userinfo.email`, `userinfo.profile`. `calendar.events` is only requested when the `meeting_request` flag is on |
| Env | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` |

- **Pilots can start immediately in Testing mode** (up to 100 named test users, a "Google hasn't
  verified this app" warning, refresh tokens expire after 7 days). Add each pilot user as a test user.
- **Public launch needs verification.** `gmail.readonly` and `gmail.compose` are *restricted*
  scopes, which require Google's app verification **and an annual third-party security assessment
  (CASA)**. Start the verification request and pick a CASA assessor early; it takes weeks and has a
  cost. Prepare: privacy policy and homepage on a verified domain, a demo video of the consent
  flow, a written justification for each scope, and the data-handling description from
  `docs/spec.md` (internal-only mail is never stored; bodies are never logged).

## 3. Slack

Create a Slack app (distribution on) in a test workspace.

| Setting | Value |
|---|---|
| OAuth redirect | `{PUBLIC_API_URL}/api/v1/slack/oauth/callback` |
| Bot scopes | `chat:write`, `im:write`, `users:read`, `users:read.email`, `channels:read` |
| Event subscriptions URL | `{PUBLIC_API_URL}/api/v1/slack/events` |
| Interactivity URL | `{PUBLIC_API_URL}/api/v1/slack/interactions` |
| Env | `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET` |

Without `SLACK_SIGNING_SECRET` the API rejects every Slack request outside local mock mode. This is
intended.

## 4. Email delivery (invites and set-password links)

`get_email_sender()` uses SMTP outside local/test. Point `SMTP_HOST`/`SMTP_PORT` at your provider
(or implement the Resend sender key), and set `WEB_URL` to the public web origin: the links in
emails are `{WEB_URL}/invite/{token}` and `{WEB_URL}/set-password?token=...`.

## 5. Deploy

- **API + workers + Postgres + Redis:** `docs/deploy-staging.md` (compose, Caddy). For a connected
  environment set `MOCK_API=false`, `APP_ENV=staging`, and run the Celery worker and beat
  (`uv run celery -A app.workers.celery_app worker -Q sync,run,executor,notify,default -l info`
  and `... beat`). Nothing executes approved actions or syncs on a schedule without them.
- **Web (Vercel or any Node host):** `NEXT_PUBLIC_API_BASE=https://api.<domain>`,
  `API_JWT_SECRET` (identical to the API's), `SESSION_SECRET`. Build with `next build`.
- **Reverse proxy:** forward the real client IP (`X-Forwarded-For`) so the per-IP login rate limit
  does not treat every user as one.
- **CI:** push the repository; `.github/workflows/ci.yml` (API) and `web.yml` (web + browser E2E)
  have never run on GitHub yet. Fix whatever the first run shows.

## 6. The proof run (the Phase 1 exit criterion)

With HubSpot, Google and Slack connected to test accounts:

1. Onboard a client from the Platform Admin portal; sign in as its Owner and finish onboarding.
2. Let the first sync finish; open Today. Confirm real companies and a ranked list.
3. Open a finding; every sentence has evidence chips and "Not confirmed" is honest.
4. Approve an email: a **draft appears in the test Gmail**, nothing is sent.
5. Approve a CRM field update: HubSpot changes; **Revert** restores it.
6. Approve from Slack; the Inbox and the log update within seconds.
7. Decision log: replay shows evidence, rules, the edit diff and the execution.

Record this run (screens + the log export). It is the evidence for the pilot and for Google's review.

## Known limits to say out loud

- Explanations and drafts are rule-based templates until the AI service is connected through
  `/internal/v1` (`docs/ai-integration.md`).
- Email digests, result tracking, learning from edits, support/billing signals and Salesforce are
  Phase 2/3 (see the product blueprint).
- Tier 1 (internal-only) actions run by themselves once a worker is running.
