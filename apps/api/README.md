# RevOps Agent API (apps/api)

FastAPI + SQLAlchemy 2 (async) + PostgreSQL 16 with RLS + Redis + Celery. Python 3.12, managed by `uv`.
Read `../../agent.md` first (hard rules), then `../../docs/conventions.md`.

## Quick start
```bash
make up            # Postgres (host port 5433), Redis, Mailpit (:8025)
cp ../../.env.example .env
make migrate       # alembic upgrade head (as the owner role)
make seed          # Demo SaaS + Other Co (idempotent)
make api           # http://localhost:8000/docs
MOCK_API=true make api   # every endpoint served with realistic stateful mock data
```
`make dev` = `up` + `api`. `make test` (needs Docker; starts disposable Postgres/Redis), `make lint`, `make fmt`.

## Calling the API
`uv run python scripts/mint_jwt.py manager` prints a service JWT for the seeded Demo SaaS org.
`curl -H "Authorization: Bearer $T" localhost:8000/api/v1/me`. A Bruno collection is generated into `../../bruno/`
(`PYTHONPATH=. uv run python scripts/gen_bruno.py`).

## Modes
| Env | Behaviour |
|---|---|
| `MOCK_API=false` (default) | implemented endpoints are real; the rest answer `501 not_implemented` (but exist in OpenAPI) |
| `MOCK_API=true` | every endpoint is served from `app/mocks/*.json` (in-memory state for cards/findings/notifications) |
| `REAL_ROUTERS=me,orgs` | those groups use real code even in mock mode |
| `MOCK_AUTH=false` | skip JWT/role checks in mock mode (UI prototyping) |
Mock helpers: header `X-Mock-Error: <error_code>`, header `X-Mock-Empty: true`.

## Layout
`app/contract.py` endpoint registry + dispatcher · `routes/` contract stubs · `schemas/` Pydantic models ·
`services/` business logic · `models/` SQLAlchemy · `auth/` JWT + deps · `permissions.py` role matrix ·
`db/` session, RLS helper · `connectors/` provider framework · `ports/` AI seam · `workers/` Celery ·
`mocks/` mock data + handlers · `utils/` crypto, locks, pagination, rate limit, ids, canonical JSON ·
`internal_app.py` `/internal/v1` AI service API (own OpenAPI) · `migrations/` Alembic.

## Generated artifacts (commit them with the change)
`make docs-gen` → `docs/endpoints.md`, `docs/error-codes.md`, `app/mocks/*.json` · `make openapi-snapshot` → `tests/snapshots/*.json`.

## Operations
Staging: `../../docs/deploy-staging.md`. CI: `.github/workflows/ci.yml`. Phase 0 hand-off: `../../docs/handoff-p0.md`.
