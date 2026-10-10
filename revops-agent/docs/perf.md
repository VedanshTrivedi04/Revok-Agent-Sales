# Performance (`docs/perf.md`)

Only numbers that were actually measured are listed here, with how to reproduce them. An earlier
revision of this file contained a 50 orgs x 500 accounts results table that had **not** been
produced by any run; it has been removed.

## 1. Measured: one org, 500 accounts, in-process (`scripts/bench_api.py`)
Setup: throw-away database on the dev Postgres 16 (Docker Desktop, Windows), Redis 7, real RLS and
auth path (JWT + membership cache), single uvicorn-equivalent process (ASGI in-process, so no
network). Seed: 500 accounts, 1,500 contacts, 10,000 events, 6,000 usage snapshots, 250 findings
(6 evidence each), 250 cards. 100 sequential requests per endpoint after a 5-request warm-up, then
the same endpoint hit by 20 concurrent clients.

| Endpoint | p50 ms | p95 ms | p99 ms | p95 ms @ 20 concurrent |
|---|---|---|---|---|
| `GET /today?owner=all` | 30 | 101 | 154 | 1267 |
| `GET /accounts?limit=50` | 12 | 14 | 15 | 280 |
| `GET /accounts?query=` | 10 | 14 | 15 | 310 |
| `GET /accounts/{id}` | 14 | 20 | 22 | 286 |
| `GET /accounts/{id}/timeline` | 9 | 11 | 13 | 231 |
| `GET /findings/{id}` | 12 | 16 | 17 | 230 |
| `GET /action-cards?limit=25` | 11 | 13 | 16 | 265 |

Reading it:
- **Sequential latency meets the plan targets** (Today p95 < 800 ms, accounts list p95 < 500 ms) with a wide margin.
- **Under 20 concurrent clients on ONE process, latency is queueing**, not query time: the process is CPU-bound
  on a single event loop. `GET /today` is the heaviest (p95 1.27 s at 20 concurrent), which exceeds the 800 ms
  target in that configuration. Production should run several workers (`uvicorn --workers N` or one container per
  core); throughput scales with workers because the database is nowhere near saturated. Re-measure with the real
  topology before sign-off.
- The benchmark found a real defect (12 accounts/runs/entity-review handlers crashed because of a handler
  signature mismatch). That is fixed and covered by `tests/test_permission_matrix_endpoints.py`.

Reproduce: `cd apps/api && PYTHONPATH=. uv run python scripts/bench_api.py --accounts 500 --requests 100 --concurrency 20`
(creates and drops its own database).

## 2. Not yet measured (do not quote targets as achieved)
- 50 orgs x 500 accounts sustained load: `tests/load/locustfile.py` exists but has **not been run**; it needs a
  deployed stack with several workers.
- Nightly run for 500 accounts (< 5 min target): not timed.
- Sync fan-out under load and Celery queue latency.

## 3. Tuning already applied
- Async engine pool `pool_size=10, max_overflow=20` (default 5 + 10 starved concurrent requests).
- `ix_findings_org_id_status_priority_score` (Today), trigram index `ix_accounts_name_trgm` (account search),
  aggregated usage trend query (no N+1; accounts list is a fixed number of queries).
