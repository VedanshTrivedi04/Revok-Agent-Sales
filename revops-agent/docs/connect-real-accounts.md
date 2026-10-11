# Connect the real HubSpot, Google and Slack (step by step)

For: the developer who owns the accounts. Do the steps in order; each ends with a check that tells
you it works before you move on. Use **test accounts only** (a HubSpot test portal, a throw-away
Google user, a test Slack workspace). The settings and reasons behind them are in `go-live.md`.

At any point, `uv run python scripts/integration_doctor.py` (in `apps/api`) tells you what is still
missing and prints the exact URLs to register.

## 0. One-time local setup

1. Start the stack as in `testing-guide.md` section 0, but keep these extra variables in the API window:

```powershell
# generate once and keep: encrypts provider tokens at rest
python -c "import os,base64;print('k1:'+base64.b64encode(os.urandom(32)).decode())"
$env:TOKEN_ENC_KEYS="<paste the k1:... value>"
$env:INTERNAL_API_KEY="local-internal-key-1234567890"
```

2. **Run the background worker and scheduler** (without them nothing syncs and approved actions never
   execute). Windows cannot use the default pool; use `-P solo`. Two more windows, same env variables:

```powershell
uv run celery -A app.workers.celery_app worker -Q sync,run,executor,notify,default -l info -P solo
uv run celery -A app.workers.celery_app beat -l info
```

3. **Slack only**: Slack calls your server, so it needs a public HTTPS address. Start a tunnel
   (`ngrok http 8100` or `cloudflared tunnel --url http://localhost:8100`), and set
   `$env:PUBLIC_API_URL="https://<your-tunnel-host>"` before starting the API. HubSpot and Google
   accept `http://localhost`, but using the same tunnel URL for all three keeps one set of redirect URLs.

## 1. HubSpot

1. developers.hubspot.com -> create a developer account -> **Create app**. Also create a **test
   account** (portal) and add ~10 companies with contacts, deals, a renewal date, ARR, seats, plan and a
   health property (Green / At Risk / Red) so there is something to analyse.
2. App -> **Auth**: add the redirect URL `{PUBLIC_API_URL}/api/v1/oauth/hubspot/callback` and the
   scopes listed in `go-live.md` section 1. Copy the Client ID and secret.
3. API window: `$env:HUBSPOT_CLIENT_ID="..."; $env:HUBSPOT_CLIENT_SECRET="..."`, restart the API.
4. **Check:** the doctor shows hubspot PASS. In the web app (as Olivia or a workspace you created),
   open `/onboarding/hubspot` -> Connect HubSpot -> approve in the test portal. You return to the
   same step with "Connected" and a portal name.
5. **Check:** `/onboarding/field-mapping`: dropdowns list your real HubSpot properties; map them, Save,
   and the preview shows three of your real companies with ARR/renewal/seats.
6. **Check:** `/onboarding/first-sync` (or Settings -> Integrations -> Sync now): the worker window
   logs the sync; Accounts fills with your companies; Settings -> Integrations -> Sync history shows a
   successful run. Run **Sync now** again: nothing changes (it is idempotent).

If it fails: the error is on the Integrations page (`last_error`) and in the API/worker log. A
redirect mismatch is HubSpot's "redirect_uri_mismatch": re-register the exact URL the doctor prints.

## 2. Google (Gmail and Calendar)

1. console.cloud.google.com -> new project -> enable the **Gmail API** and **Google Calendar API**.
2. **OAuth consent screen**: External, **Testing**; add yourself (and each pilot user) under **Test users**;
   add the scopes from `go-live.md` section 2.
3. **Credentials -> OAuth client ID** (Web): add both redirect URIs the doctor prints
   (`.../oauth/gmail/callback` and `.../oauth/gcal/callback`).
4. API window: `$env:GOOGLE_CLIENT_ID="..."; $env:GOOGLE_CLIENT_SECRET="..."`, restart the API.
5. **Check:** `/onboarding/google` -> Connect Gmail (accept the "unverified app" warning; it is expected
   in Testing mode) and Connect Calendar. Both show Connected with your email.
6. **Check:** send yourself an email from an address on a customer's domain (or reply to one of your
   test contacts) and create a calendar event with a customer attendee. After the next sync the account
   Timeline shows them; internal-only mail is **not** stored.
7. **Check:** approve an email card -> the worker log shows the execution and a **draft appears in
   Gmail Drafts**. Nothing is sent. Reverting the card deletes the draft.

## 3. Slack

1. api.slack.com/apps -> Create New App (from scratch) in your test workspace.
2. **OAuth & Permissions**: redirect URL `{PUBLIC_API_URL}/api/v1/slack/oauth/callback`; bot scopes
   `chat:write`, `im:write`, `users:read`, `users:read.email`, `channels:read`.
3. **Event Subscriptions**: Request URL `{PUBLIC_API_URL}/api/v1/slack/events` (it must verify
   immediately: the API answers Slack's challenge). **Interactivity**: Request URL
   `{PUBLIC_API_URL}/api/v1/slack/interactions`.
4. Copy Client ID, Client Secret and the **Signing Secret** (Basic Information).
5. API window: `$env:SLACK_CLIENT_ID=...; $env:SLACK_CLIENT_SECRET=...; $env:SLACK_SIGNING_SECRET=...`,
   restart the API.
6. **Check:** `/onboarding/slack` -> Add to Slack -> Allow. Back in the app, the member table lists
   your Slack users, matched by email; Save links.
7. **Check:** a new Tier 2 card for a linked owner arrives as a **Slack message with Approve / Reject**.
   Click Approve: the message updates in place, and the card in the web Inbox shows approved, and the
   Decision log entry says channel `slack`. A forged request (wrong signature) is rejected.

## 4. The proof run (do this once everything above is green)

1. Platform Admin -> **Onboard client** for a fresh workspace; sign in as its Owner; finish onboarding.
2. Today shows real companies ranked. Open the top finding: every sentence has evidence chips that
   open the real HubSpot / Gmail / Calendar record.
3. Approve an email (draft in Gmail), a task (task in HubSpot), a field update (HubSpot property
   changes; then **Revert** restores it). Approve one from Slack.
4. Decision log -> Why Replay for each: evidence, rules, edit diff, execution.
5. Record the screen and export the log (Settings -> Data). This is your evidence for pilots and for
   Google's verification review.

## Troubleshooting quick table

| Symptom | Cause | Fix |
|---|---|---|
| "X is not set up on this server yet" when pressing Connect | provider env variables empty | set them, restart the API (doctor shows which) |
| Provider says redirect_uri mismatch | registered URL differs from `PUBLIC_API_URL` | register exactly what the doctor prints |
| Connected but nothing syncs | worker/beat not running | start the two Celery windows |
| Approved card stays "approved" | worker not running (or no connection for that provider) | start the worker; check Integrations status |
| Slack "url verification failed" | tunnel not running or `PUBLIC_API_URL` not the tunnel | restart the API with the tunnel URL |
| Slack buttons do nothing | wrong or missing signing secret | set `SLACK_SIGNING_SECRET`, restart |
| Google refresh stops after 7 days | Testing-mode token expiry | reconnect (expected until the app is verified) |
