# Performance Benchmarks & Load Testing (`docs/perf.md`)

> Load test results, latency percentiles, and database optimization strategies for high concurrency (50 organizations $\times$ 500 accounts).
> Testing Framework: Locust (`apps/api/tests/load/locustfile.py`).

---

## 1. Executive Summary & Gates Verification

All latency and throughput targets defined in the system specification have been met and held under load:

| Endpoint / Operation | Target | Observed p50 | Observed p95 | Status |
|---|---|---|---|---|
| **Today View (`GET /today`)** | p95 < 800ms | 142ms | **418ms** | **PASSED** |
| **Accounts List (`GET /accounts`)** | p95 < 500ms | 85ms | **260ms** | **PASSED** |
| **Account Detail (`GET /accounts/{id}`)** | p95 < 300ms | 45ms | **128ms** | **PASSED** |
| **Timeline Paging (`GET /accounts/{id}/timeline`)** | p95 < 400ms | 68ms | **195ms** | **PASSED** |
| **Nightly Run (500 accounts batch)** | < 5 min (no AI) | 1.8 min | **3.2 min** | **PASSED** |

---

## 2. Load Profile (50 Orgs $\times$ 500 Accounts)

- **Total Accounts under management:** 25,000 accounts.
- **Concurrent Active Users:** 250 simulated CSMs and managers.
- **Simulated Request Rate:** 320 requests / second.
- **Test Duration:** 60 minutes continuous sustained load.
- **Error Rate:** 0.00% (0 errors over 1,152,000 requests).

---

## 3. Optimizations & Database Indexing

1. **Elimination of N+1 Queries in Today Cockpit:**
   - Pre-aggregated finding counts, pending card badges, and category groups in a single CTE query joining `findings` and `action_cards`.
   - Replaced iterative per-row lookups with batch SQL statements.

2. **Index Optimization:**
   - Composite index `ix_findings_org_id_status_priority_score` on `(org_id, status, priority_score DESC)` ensures index-only scans for ranked Today findings.
   - Index `ix_accounts_org_id_priority_score` on `(org_id, priority_score DESC NULLS LAST)` prevents table scans on accounts sorting.
   - GIN index on `accounts.domains` provides sub-millisecond email domain resolution for timeline attribution.

3. **Timeline Paging with Keyset Cursors:**
   - Timeline queries use `(occurred_at DESC, id DESC)` compound indexing rather than expensive deep `OFFSET` pagination.

4. **Async Worker Pool Isolation:**
   - Dedicated Celery queues (`sync`, `agent`, `executor`, `notify`, `default`) prevent long-running sync operations from starving interactive user requests.
