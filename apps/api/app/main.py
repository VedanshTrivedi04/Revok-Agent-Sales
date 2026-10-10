import logging
from typing import Any

import sentry_sdk
import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routes import health
from app.utils.errors import AppError


def _envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ]
    )
    if settings.sentry_dsn:
        # Never ship request bodies or PII (agent.md hard rule 10).
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.app_env,
            send_default_pii=False,
            max_request_body_size="never",
        )

    app = FastAPI(title="RevOps Agent API", version="0.1.0")
    app.include_router(health.router)

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(_envelope(exc.code, exc.message, exc.details), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(
            _envelope("validation_error", "Invalid request", {"errors": errors}), status_code=422
        )

    return app


app = create_app()
