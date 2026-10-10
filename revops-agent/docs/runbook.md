# Operations Runbook (`docs/runbook.md`)

> Production and Staging Runbook for RevOps platform operators, SREs, and engineers.
> Covers backup/restore drills, organization purges, dead-letter jobs, token revocation, and disaster recovery.

---

## 1. Backup & Recovery Strategy

### 1.1 Recovery Objectives
- **RPO (Recovery Point Objective):** $\le$ 5 minutes.
- **RTO (Recovery Time Objective):** $\le$ 30 minutes.

### 1.2 Automated Backups
1. **PostgreSQL Database:**
   - **Daily Full Snapshot:** Physical basebackup taken daily at 01:00 UTC using `pg_dump` / WAL-G to secure object storage (S3/GCS) with KMS encryption.
   - **Continuous Archiving:** Write-Ahead Logging (WAL) archiving every 60 seconds enables Point-In-Time-Recovery (PITR).
2. **Redis:**
   - AOF (Append-Only File) enabled with `appendfsync everysec`.
   - Snapshot RDB written every 15 minutes.

### 1.3 Restore Drill Procedure (Quarterly Verification)
To verify recovery without affecting active traffic:

```bash
# 1. Spin up an isolated staging database container
docker run -d --name restore-drill-pg -e POSTGRES_PASSWORD=restore_test -p 5433:5432 postgres:16

# 2. Restore the latest daily dump
psql -h localhost -p 5433 -U postgres -d revops < /backup/daily/revops_latest.sql

# 3. Run schema and data validation checks
uv run python scripts/data_health.py --host localhost --port 5433

# 4. Verify decision log tamper-evident hash chain integrity
uv run pytest tests/test_decision_log.py

# 5. Clean up drill environment
docker rm -f restore-drill-pg
```

---

## 2. Organization Lifecycle & Purge Procedures

### 2.1 Soft Deletion (`DELETE /orgs/current`)
- Sets `organizations.status = 'deleted'` and `organizations.deleted_at = now()`.
- Immediately revokes provider tokens (`status = 'disconnected'`, encrypted tokens cleared).
- Cancels in-flight and pending `AgentRun`s.
- Emits `org.deleted` event to SSE and logs to decision log.

### 2.2 Permanent Tenant Purge (After 30 Days)
Customer data retention policy mandates hard deletion after 30 days.

```bash
# Execute purge task through Celery maintenance queue
uv run celery -A app.workers.celery_app call maintenance.purge_deleted_org --args='["<ORG_UUID>"]'
```

**Guarantees:**
- Executes via `admin_session` connecting under PostgreSQL admin role (bypassing RLS).
- Deletes in reverse topological order across all tenant tables.
- Guarantees 0 rows remaining for `org_id`.
- Emits structured platform log `org.purged`.

---

## 3. Incident Management & Operator Tasks

### 3.1 Dead-Letter Job Inspection & Discard
When a Celery background job fails repeatedly:
1. Inspect dead-letter jobs: `GET /api/v1/admin/jobs`.
2. Retry job: `POST /api/v1/admin/jobs/{job_id}/retry`.
3. Discard unrecoverable job: `POST /api/v1/admin/jobs/{job_id}/discard`.

### 3.2 Immediate Token Revocation
If a provider API key or OAuth token is suspected to be compromised:
1. Target the integration: `POST /api/v1/integrations/{id}/disconnect`.
2. All encrypted token records are overwritten with empty bytes.
3. Associated Celery workers cease scheduling sync tasks immediately.

### 3.3 Org Suspension Guard
In the event of payment failure or abuse:
1. Suspend org: `POST /api/v1/admin/orgs/{org_id}/suspend`.
2. Global dependency returns `403 org_suspended` across all non-admin endpoints.
3. Nightly beat fan-out skips suspended organizations automatically.
