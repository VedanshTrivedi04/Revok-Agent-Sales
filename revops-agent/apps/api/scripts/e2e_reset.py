"""Puts a LOCAL database into the exact state the browser E2E tests expect.

Deletes the demo workspaces ("Demo SaaS", "Other Co") and their demo users, then seeds them again
(`seed_demo`, demo sign-ins, `seed_portfolio`). It refuses to run unless every database URL points
at localhost, so it can never wipe a shared or hosted database.

Run: uv run python scripts/e2e_reset.py
"""

import asyncio
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.config import LOCAL_ENVS, get_settings  # noqa: E402
from app.db.session import get_admin_engine, get_engine  # noqa: E402
from app.mocks import data as D  # noqa: E402
from scripts.seed_demo import seed_demo, seed_demo_logins  # noqa: E402
from scripts.seed_portfolio import seed_portfolio  # noqa: E402

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def assert_local_only() -> None:
    s = get_settings()
    if s.app_env not in LOCAL_ENVS:
        raise SystemExit(f"refusing to reset: APP_ENV={s.app_env} is not local/test")
    for name in ("database_url", "database_admin_url", "database_migrator_url"):
        host = urlparse(getattr(s, name).replace("+asyncpg", "").replace("+psycopg", "")).hostname
        if host not in LOCAL_HOSTS:
            raise SystemExit(f"refusing to reset: {name} points at {host!r}, not localhost")


async def reset() -> None:
    assert_local_only()
    url = get_settings().database_migrator_url.replace("+psycopg", "+asyncpg")
    engine = create_async_engine(url)
    async with engine.begin() as c:
        await c.execute(
            text("DELETE FROM organizations WHERE id = ANY(:ids)"),
            {"ids": [D.ORG_ID, D.OTHER_ORG_ID]},
        )
        await c.execute(
            text(
                "DELETE FROM users WHERE email LIKE '%@demo-saas.example.com' "
                "OR email LIKE '%@other-co.example.com' "
                "OR email = 'sam@platform.revops.example.com'"
            )
        )
    await engine.dispose()

    counts = await seed_demo()
    await seed_demo_logins()
    portfolio = await seed_portfolio()
    await get_engine().dispose()
    await get_admin_engine().dispose()
    print("e2e reset:", counts, portfolio)


if __name__ == "__main__":
    asyncio.run(reset())
