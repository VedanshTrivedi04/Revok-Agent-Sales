"""Celery app: queues, reliability settings, TenantTask base.

Conventions (agent.md section 5): every task takes `org_id` first and runs inside
`org_session(org_id)`. Pass ids, never customer content, as task arguments (they are stored in
`failed_jobs` when a task dead-letters). Async bodies run with asyncio.run per task.
"""

import asyncio
import json
import traceback as tb
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import structlog
from celery import Celery, Task
from kombu import Queue
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import session as db_session
from app.models.audit import FailedJob
from app.utils.errors import TransientError
from app.utils.redis import close_redis

log = structlog.get_logger()

QUEUES = ("sync", "run", "executor", "notify", "default")

celery_app = Celery("revops", broker=get_settings().redis_url, backend=None)
celery_app.conf.update(
    task_queues=[Queue(q) for q in QUEUES],
    task_default_queue="default",
    task_routes={
        "sync.*": {"queue": "sync"},
        "run.*": {"queue": "run"},
        "executor.*": {"queue": "executor"},
        "notify.*": {"queue": "notify"},
    },
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # fair dispatch; matters most for the run/executor queues
    task_default_retry_delay=30,
    broker_transport_options={"visibility_timeout": 3600},
    broker_connection_retry_on_startup=True,
    task_serializer="json",
    accept_content=["json"],
    imports=(
        "app.workers.tasks_maintenance",
        "app.executor",
        "app.workers.tasks_sync",
        "app.workers.tasks_slack",
        "app.workers.tasks_run",
    ),
    beat_schedule={
        "hourly-hubspot-sync": {
            "task": "sync.hourly_dispatch",
            "schedule": 3600.0,
        },
        "daily-digest-fanout": {
            "task": "notify.daily_digest_fanout",
            "schedule": 3600.0,
        },
        "nightly-account-runs": {
            "task": "run.nightly_dispatch",
            "schedule": 900.0,
        },
        "expire-cards-hourly": {
            "task": "maintenance.expire_cards_fanout",
            "schedule": 3600.0,
        },
        "sweep-approved-cards": {
            "task": "maintenance.sweep_approved_cards",
            "schedule": 300.0,
        },
        "purge-deleted-orgs-daily": {
            "task": "maintenance.purge_deleted_orgs_fanout",
            "schedule": 86400.0,
        },
    },
)


async def _record_failed_job(
    task_name: str, args: tuple[Any, ...], exc: BaseException, trace: str
) -> None:
    from app.db.session import admin_session

    async with admin_session() as s:
        await s.execute(
            insert(FailedJob).values(
                task_name=task_name,
                args=json.loads(json.dumps(list(args), default=str)),
                error=f"{type(exc).__name__}: {exc}"[:2000],
                traceback=trace[-8000:],
            )
        )


class TenantTask(Task):  # type: ignore[misc]
    """Retries TransientError with exponential backoff; dead-letters everything else."""

    autoretry_for = (TransientError,)
    retry_backoff = 2
    retry_backoff_max = 120
    retry_jitter = True
    max_retries = 5
    acks_late = True
    reject_on_worker_lost = True

    def on_failure(self, exc: Exception, task_id: str, args: Any, kwargs: Any, einfo: Any) -> None:
        trace = "".join(tb.format_exception(type(exc), exc, exc.__traceback__))
        log.error("task_failed", task=self.name, task_id=task_id, exc_type=type(exc).__name__)
        asyncio.run(_record_failed_job(self.name, tuple(args), exc, trace))


def tenant_task(
    name: str, *, queue: str = "default", **opts: Any
) -> Callable[[Callable[..., Awaitable[Any]]], Any]:
    """Register `async def fn(session, org_id, *args, **kwargs)` as a Celery task.

    The task opens `org_session(org_id)` (RLS context) before calling the function.
    """

    def deco(fn: Callable[..., Awaitable[Any]]) -> Any:
        async def runner(org_id: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
            # fresh engine/redis per asyncio.run: their connections are bound to the loop
            db_session.get_engine.cache_clear()
            db_session._sessionmaker.cache_clear()
            try:
                async with db_session.org_session(UUID(str(org_id))) as session:
                    structlog.contextvars.bind_contextvars(org_id=str(org_id), task=name)
                    session_arg: AsyncSession = session
                    return await fn(session_arg, UUID(str(org_id)), *args, **kwargs)
            finally:
                await db_session.get_engine().dispose()
                await close_redis()
                structlog.contextvars.clear_contextvars()

        @celery_app.task(base=TenantTask, bind=True, name=name, queue=queue, **opts)
        def task(self: Task, org_id: str, *args: Any, **kwargs: Any) -> Any:
            return asyncio.run(runner(org_id, args, kwargs))

        task.async_fn = fn
        return task

    return deco
