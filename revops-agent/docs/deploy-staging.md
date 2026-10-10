# Staging deploy (mock mode)

Goal: the frontend developer gets a stable URL that serves **every endpoint** in `docs/endpoints.md`
(mock mode on a seeded database), with HTTPS and CORS for the web origin.

## What runs
`infra/docker-compose.staging.yml`: **api** (FastAPI, `MOCK_API=true`, migrations + demo seed on start) +
**postgres 16** + **redis 7** + optional **caddy** (automatic HTTPS, profile `https`).

## First deploy (any Linux VM with Docker, ports 80/443 open, DNS A record to the VM)
```bash
git clone <repo> && cd revops-agent
cp infra/.env.staging.example infra/.env.staging
# edit: DB_OWNER_PASSWORD, API_JWT_SECRET (shared with the web app), INTERNAL_API_KEY,
#       STAGING_DOMAIN, CORS_ORIGINS, WEB_URL, PUBLIC_API_URL
docker compose -f infra/docker-compose.staging.yml --env-file infra/.env.staging --profile https up -d --build
curl https://$STAGING_DOMAIN/health            # {"status":"ok"}
curl https://$STAGING_DOMAIN/health/ready      # db + redis ok
curl https://$STAGING_DOMAIN/docs              # Swagger, tagged by portal page
```
Without a domain (LAN/laptop): omit `--profile https`; the API is on `http://<host>:${API_PORT:-8080}`.

## Calling it
The web app mints a service JWT (HS256, `aud=revops-api`, claims `sub`, `org_id`, `exp`). For manual calls:
```bash
cd apps/api && API_JWT_SECRET=<same secret> uv run python scripts/mint_jwt.py manager
curl -H "Authorization: Bearer $TOKEN" https://$STAGING_DOMAIN/api/v1/today?owner=all
```
Seed identities (Demo SaaS): `owner admin manager member viewer` (ids printed by `scripts/seed_demo.py`).
Mock helpers: header `X-Mock-Error: card_not_pending` forces any registered error; `X-Mock-Empty: true`
returns empty lists. `MOCK_AUTH=false` skips JWT/role checks (quick UI prototyping only).

## Updates
`git pull && docker compose ... up -d --build`. Migrations run on container start (`RUN_MIGRATIONS=true`);
the seed is idempotent. Mock state lives in API process memory and resets on restart.

## Switching endpoints from mock to real
`REAL_ROUTERS=me,orgs` (group names from `docs/endpoints.md`) serves those groups with real code on
the same staging URL. When `MOCK_API=false`, implemented endpoints are real and the rest return
`501 not_implemented`.

## Known limits / security notes
- Postgres is not published to the host; the dev passwords for the `app`/`admin` roles in
  `infra/db/init.sql` are acceptable only because of that. Change them for anything internet-reachable.
- Staging data is synthetic. Never load customer data into staging.
- `MOCK_AUTH=true` keeps real JWT verification; the shared `API_JWT_SECRET` is the only trust anchor.
- **Status:** the stack was built and verified locally (migrate, seed, `/health`, `/health/ready`,
  `/api/v1/today`, CORS preflight). A public staging URL needs a VM + domain, which is an
  infrastructure decision for the team (see `docs/handoff-p0.md`, open items).
