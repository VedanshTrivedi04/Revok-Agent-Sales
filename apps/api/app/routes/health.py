from fastapi import APIRouter, Response
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings

router = APIRouter(tags=["Health"])


class HealthOut(BaseModel):
    status: str


class ReadyOut(BaseModel):
    status: str
    checks: dict[str, str]


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    return HealthOut(status="ok")


async def _check_db() -> str:
    engine = create_async_engine(get_settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "down"
    finally:
        await engine.dispose()


async def _check_redis() -> str:
    client = Redis.from_url(get_settings().redis_url)
    try:
        await client.ping()
        return "ok"
    except Exception:
        return "down"
    finally:
        await client.aclose()


@router.get("/health/ready", response_model=ReadyOut)
async def ready(response: Response) -> ReadyOut:
    checks = {"db": await _check_db(), "redis": await _check_redis()}
    ok = all(v == "ok" for v in checks.values())
    if not ok:
        response.status_code = 503
    return ReadyOut(status="ready" if ok else "not_ready", checks=checks)
