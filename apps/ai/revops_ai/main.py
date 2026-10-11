"""Process entry point of the AI service.

    uv run uvicorn revops_ai.main:app --host 0.0.0.0 --port 8100

Everything is configured by environment (see .env.example). It starts without the model endpoint
or the backend being reachable: runs then fall back to the template result and /health?deep=true
reports the model as down.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from revops_ai.adapters.internal_client import InternalClient
from revops_ai.config import get_settings
from revops_ai.graph.runner import checkpointer
from revops_ai.llm.client import OpenAICompatClient
from revops_ai.observability.tracing import sink_from_settings
from revops_ai.service import create_service

log = structlog.get_logger()


def build() -> FastAPI:
    cfg = get_settings()
    client = InternalClient(cfg)

    @asynccontextmanager
    async def lifespan(root: FastAPI) -> AsyncIterator[None]:
        async with checkpointer(cfg.checkpoint_dsn or None) as saver:
            service = create_service(
                OpenAICompatClient(cfg), client, saver, settings=cfg, sink=sink_from_settings(cfg)
            )
            root.mount("/", service)
            log.info(
                "ai_service_started",
                model=cfg.llm_model,
                checkpoints="postgres" if cfg.checkpoint_dsn else "memory",
            )  # noqa: E501
            try:
                yield
            finally:
                await client.http.aclose()

    return FastAPI(title="RevOps AI service", lifespan=lifespan, docs_url=None, redoc_url=None)


app = build()
