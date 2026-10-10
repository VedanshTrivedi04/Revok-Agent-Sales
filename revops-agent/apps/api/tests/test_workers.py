import asyncio
from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.utils.errors import FatalError, TransientError
from app.utils.locks import LockNotAcquired, lock
from app.workers.celery_app import QUEUES, TenantTask, celery_app, tenant_task
from app.workers.tasks_maintenance import ping
from tests.helpers import SeededOrg

CALLS: dict[str, int] = {}


@tenant_task("test.flaky", queue="default", max_retries=3)
async def flaky(session: AsyncSession, org_id: UUID, key: str, fail_times: int) -> str:
    CALLS[key] = CALLS.get(key, 0) + 1
    if CALLS[key] <= fail_times:
        raise TransientError("temporary")
    return "ok"


@tenant_task("test.always_transient", queue="default", max_retries=2)
async def always_transient(session: AsyncSession, org_id: UUID, key: str) -> None:
    CALLS[key] = CALLS.get(key, 0) + 1
    raise TransientError("still down")


@tenant_task("test.fatal", queue="default")
async def fatal(session: AsyncSession, org_id: UUID, key: str) -> None:
    CALLS[key] = CALLS.get(key, 0) + 1
    raise FatalError("stale_preview")


@pytest.fixture(autouse=True)
def eager() -> Iterator[None]:
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=False)
    yield
    celery_app.conf.update(task_always_eager=False)


def _sync_engine() -> Any:
    return create_engine(get_settings().database_migrator_url)


def _failed(task_name: str, key: str) -> list[Any]:
    with _sync_engine().connect() as c:
        return list(
            c.execute(
                text(
                    "SELECT error, args FROM failed_jobs WHERE task_name = :t AND args::text LIKE :k"
                ),
                {"t": task_name, "k": f"%{key}%"},
            )
        )


def test_queues_and_reliability_settings() -> None:
    names = {q.name for q in celery_app.conf.task_queues}
    assert names == set(QUEUES) == {"sync", "run", "executor", "notify", "default"}
    c = celery_app.conf
    assert c.task_acks_late and c.task_reject_on_worker_lost and c.worker_prefetch_multiplier == 1
    assert isinstance(ping, TenantTask)
    assert ping.acks_late and ping.max_retries == 5 and ping.retry_backoff == 2
    assert (
        ping.retry_backoff_max == 120
        and ping.retry_jitter
        and ping.autoretry_for == (TransientError,)
    )


def test_routes_by_prefix() -> None:
    routes = celery_app.conf.task_routes
    assert {v["queue"] for v in routes.values()} == {"sync", "run", "executor", "notify"}


def test_task_runs_inside_org_session(seeded: SeededOrg) -> None:
    result = ping.apply(args=[str(seeded.org_id)]).get()
    assert result == {"org_id": str(seeded.org_id)}


def test_transient_error_is_retried_then_succeeds(seeded: SeededOrg) -> None:
    key = uuid4().hex
    res = flaky.apply(args=[str(seeded.org_id), key, 2])
    assert res.get() == "ok" and CALLS[key] == 3
    assert _failed("test.flaky", key) == []


def test_retries_exhausted_dead_letters(seeded: SeededOrg) -> None:
    key = uuid4().hex
    res = always_transient.apply(args=[str(seeded.org_id), key])
    assert res.failed() and CALLS[key] == 3  # 1 attempt + 2 retries
    rows = _failed("test.always_transient", key)
    assert len(rows) == 1 and "TransientError" in rows[0][0]
    assert rows[0][1][0] == str(seeded.org_id)


def test_fatal_error_is_not_retried_and_dead_letters(seeded: SeededOrg) -> None:
    key = uuid4().hex
    res = fatal.apply(args=[str(seeded.org_id), key])
    assert res.failed() and CALLS[key] == 1
    assert len(_failed("test.fatal", key)) == 1


# ------------------------------------------------------------------ locks
async def test_lock_is_exclusive_and_released() -> None:
    key = f"test:{uuid4().hex}"
    async with lock(key, ttl=30):
        with pytest.raises(LockNotAcquired):
            async with lock(key, ttl=30):
                pass
    async with lock(key, ttl=30):  # released on exit
        pass


async def test_lock_released_on_exception_and_wait_acquires() -> None:
    key = f"test:{uuid4().hex}"
    with pytest.raises(RuntimeError):
        async with lock(key, ttl=30):
            raise RuntimeError("boom")

    async def holder() -> None:
        async with lock(key, ttl=30):
            await asyncio.sleep(0.3)

    t = asyncio.create_task(holder())
    await asyncio.sleep(0.05)
    async with lock(key, ttl=30, wait=2.0):
        pass
    await t


async def test_lock_expires_by_ttl() -> None:
    key = f"test:{uuid4().hex}"
    cm = lock(key, ttl=1)
    await cm.__aenter__()
    await asyncio.sleep(1.2)
    async with lock(key, ttl=5):  # previous holder's TTL elapsed
        pass
    await cm.__aexit__(None, None, None)  # stale release must not delete the new owner's lock
