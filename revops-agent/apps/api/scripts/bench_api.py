"""Reproducible API latency benchmark on a throw-away database.

Creates database `bench_<random>` on the dev Postgres (localhost:5433 by default), migrates it,
seeds ONE org with N accounts (contacts, events, 12 weeks of usage, findings with evidence, cards),
measures the read endpoints in-process (ASGI, real Postgres + Redis) and prints a markdown table.
Everything is dropped afterwards.

    cd apps/api && PYTHONPATH=. uv run python scripts/bench_api.py --accounts 500 --requests 200

This is a single-process benchmark of the application + database, not a network load test; for
the 50 orgs x 500 accounts profile use tests/load/locustfile.py against a deployed stack.
"""

import argparse
import asyncio
import os
import statistics
import sys
import time
from pathlib import Path
from uuid import uuid4

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

API_ROOT = Path(__file__).resolve().parents[1]
ADMIN_DSN = os.environ.get("BENCH_ADMIN_DSN", "postgresql://owner:owner@localhost:5433/postgres")
HOST_PORT = "localhost:5433"

SEED_SQL = """
INSERT INTO organizations (id, name, status) VALUES (%(org)s, 'Bench Org', 'active');
INSERT INTO users (id, email, name) VALUES (%(user)s, 'bench-owner@example.com', 'Bench Owner');
INSERT INTO memberships (id, org_id, user_id, role) VALUES (gen_random_uuid(), %(org)s, %(user)s, 'owner');

INSERT INTO accounts (id, org_id, name, domains, arr, plan_name, seats_purchased, renewal_date,
                      crm_health, status, owner_user_id, risk_level, priority_score, last_activity_at)
SELECT gen_random_uuid(), %(org)s, 'Account ' || g, ARRAY['acct' || g || '.example.com'],
       (random() * 200000)::numeric(14,2), 'Business', 50, current_date + (g %% 180),
       'Green', 'active', %(user)s,
       CASE WHEN g %% 4 = 0 THEN 'high' WHEN g %% 4 = 1 THEN 'medium' ELSE NULL END,
       (random() * 100)::numeric(5,2), now() - (g %% 30) * interval '1 day'
FROM generate_series(1, %(n)s) g;

INSERT INTO contacts (id, org_id, account_id, email, name, role_tags)
SELECT gen_random_uuid(), %(org)s, a.id, 'c' || k || '@' || a.domains[1], 'Contact ' || k, '{}'
FROM accounts a, generate_series(1, 3) k WHERE a.org_id = %(org)s;

INSERT INTO events (id, org_id, account_id, source, source_record_id, type, occurred_at, title)
SELECT gen_random_uuid(), %(org)s, a.id, 'gmail', md5(a.id::text || k), 'email_in',
       now() - k * interval '1 day', 'Subject ' || k
FROM accounts a, generate_series(1, 20) k WHERE a.org_id = %(org)s;

INSERT INTO usage_snapshots (id, org_id, account_id, period_start, period_end, granularity,
                             active_users, seats_used, source)
SELECT gen_random_uuid(), %(org)s, a.id, (current_date - w * 7), (current_date - w * 7 + 6), 'week',
       30 + (random() * 20)::int, 40, 'api'
FROM accounts a, generate_series(1, 12) w WHERE a.org_id = %(org)s;

INSERT INTO findings (id, org_id, account_id, type, fingerprint, status, severity, priority_score,
                      confidence, title, summary, claims, rule_keys, categories)
SELECT gen_random_uuid(), %(org)s, a.id, 'risk', md5(a.id::text), 'open',
       a.risk_level, a.priority_score, 0.8, a.name || ': usage down', 'Synthetic summary',
       '[{"text": "Usage down", "evidence_ids": ["E1"]}]'::jsonb, ARRAY['R01_usage_drop'], ARRAY['usage']
FROM accounts a WHERE a.org_id = %(org)s AND a.risk_level IS NOT NULL;

INSERT INTO finding_evidence (id, org_id, finding_id, evidence_key, kind, label)
SELECT gen_random_uuid(), %(org)s, f.id, 'E' || k, 'rule_metric', 'Evidence ' || k
FROM findings f, generate_series(1, 6) k WHERE f.org_id = %(org)s;

INSERT INTO action_cards (id, org_id, account_id, finding_id, type, tier, status, title, idempotency_key)
SELECT gen_random_uuid(), %(org)s, f.account_id, f.id, 'crm_task', 1, 'pending_approval',
       'Card ' || f.id, md5(f.id::text || 'card')
FROM findings f WHERE f.org_id = %(org)s;
"""


def pct(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(len(s) * q))]


async def main(accounts: int, requests: int, concurrency: int) -> None:
    db = f"bench_{uuid4().hex[:8]}"
    org, user = uuid4(), uuid4()
    with psycopg.connect(ADMIN_DSN, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE {db}")
    try:
        os.environ.update(
            APP_ENV="test", RATE_LIMIT_ENABLED="false", MOCK_API="false",
            DATABASE_URL=f"postgresql+asyncpg://app:app@{HOST_PORT}/{db}",
            DATABASE_ADMIN_URL=f"postgresql+asyncpg://admin:admin@{HOST_PORT}/{db}",
            DATABASE_MIGRATOR_URL=f"postgresql+psycopg://owner:owner@{HOST_PORT}/{db}",
        )  # fmt: skip
        with psycopg.connect(f"postgresql://owner:owner@{HOST_PORT}/{db}", autocommit=True) as conn:
            conn.execute("GRANT USAGE ON SCHEMA public TO app, admin")
            conn.execute(
                "ALTER DEFAULT PRIVILEGES FOR ROLE owner IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app, admin"
            )
            conn.execute(
                "ALTER DEFAULT PRIVILEGES FOR ROLE owner IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app, admin"
            )
        from alembic import command
        from alembic.config import Config

        cfg = Config(str(API_ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
        command.upgrade(cfg, "head")

        t0 = time.perf_counter()
        with psycopg.connect(f"postgresql://owner:owner@{HOST_PORT}/{db}", autocommit=True) as conn:
            for stmt in filter(str.strip, SEED_SQL.split(";" + chr(10))):
                conn.execute(stmt, {"org": org, "user": user, "n": accounts})
            conn.execute("ANALYZE")
            counts = {
                t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]  # type: ignore[index]
                for t in ("accounts", "events", "usage_snapshots", "findings", "action_cards")
            }
        print(f"seeded {accounts} accounts in {time.perf_counter() - t0:.1f}s: {counts}")

        import httpx
        from httpx import ASGITransport

        from app.main import create_app
        from tests.helpers import bearer, mint_jwt

        headers = bearer(mint_jwt(user, org))
        async with httpx.AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://b", headers=headers
        ) as c:
            acc_id = (await c.get("/api/v1/accounts?limit=1")).json()["items"][0]["id"]
            fid = (await c.get("/api/v1/findings?limit=1")).json()["items"][0]["id"]
            targets = {
                "GET /today?owner=all": "/api/v1/today?owner=all",
                "GET /accounts (50)": "/api/v1/accounts?limit=50",
                "GET /accounts?query=": "/api/v1/accounts?query=Account%2012&limit=50",
                "GET /accounts/{id}": f"/api/v1/accounts/{acc_id}",
                "GET /accounts/{id}/timeline": f"/api/v1/accounts/{acc_id}/timeline?limit=25",
                "GET /findings/{id}": f"/api/v1/findings/{fid}",
                "GET /action-cards": "/api/v1/action-cards?limit=25",
            }
            rows = []
            for name, url in targets.items():
                for _ in range(5):  # warm-up
                    assert (await c.get(url)).status_code == 200, url
                lat: list[float] = []
                for _ in range(requests):
                    t = time.perf_counter()
                    r = await c.get(url)
                    lat.append((time.perf_counter() - t) * 1000)
                    assert r.status_code == 200
                conc: list[float] = []

                async def worker(u: str = url, out: list[float] = conc) -> None:
                    for _ in range(max(1, requests // concurrency)):
                        t = time.perf_counter()
                        await c.get(u)
                        out.append((time.perf_counter() - t) * 1000)

                await asyncio.gather(*(worker() for _ in range(concurrency)))
                rows.append(
                    (name, statistics.median(lat), pct(lat, 0.95), pct(lat, 0.99), pct(conc, 0.95))
                )
        print(
            f"\n| Endpoint | p50 ms | p95 ms | p99 ms | p95 ms @ {concurrency} concurrent |\n|---|---|---|---|---|"
        )
        for name, p50, p95, p99, c95 in rows:
            print(f"| {name} | {p50:.0f} | {p95:.0f} | {p99:.0f} | {c95:.0f} |")
    finally:
        from app.db.session import get_engine

        await get_engine().dispose()
        with psycopg.connect(ADMIN_DSN, autocommit=True) as admin:
            admin.execute(f"DROP DATABASE IF EXISTS {db} WITH (FORCE)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--accounts", type=int, default=500)
    ap.add_argument("--requests", type=int, default=200)
    ap.add_argument("--concurrency", type=int, default=20)
    a = ap.parse_args()
    asyncio.run(main(a.accounts, a.requests, a.concurrency))
