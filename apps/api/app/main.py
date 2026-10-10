from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.contract import build_router
from app.internal_app import create_internal_app
from app.middleware import IdempotencyMiddleware, RequestIdMiddleware
from app.observability import configure_logging, init_sentry
from app.routes import health
from app.utils.errors import ERROR_CODES, AppError

log = structlog.get_logger()

_STATUS_TO_CODE = {400: "bad_request", 401: "unauthenticated", 403: "forbidden", 404: "not_found"}


def _envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_sentry(settings.sentry_dsn, settings.app_env)

    app = FastAPI(title="RevOps Agent API", version="0.1.0")
    app.include_router(health.router)
    app.include_router(build_router(settings))
    app.mount("/internal", create_internal_app())

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            _envelope(exc.code, exc.message, exc.details),
            status_code=exc.status,
            headers=exc.headers or None,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(
            _envelope("validation_error", ERROR_CODES["validation_error"][1], {"errors": errors}),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_TO_CODE.get(exc.status_code, "bad_request")
        return JSONResponse(
            _envelope(code, exc.detail if exc.status_code != 404 else "Not found"),
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_exception", exc_type=type(exc).__name__)  # never log message/body
        return JSONResponse(
            _envelope("internal_error", ERROR_CODES["internal_error"][1]), status_code=500
        )

    # Outermost first: request id wraps everything; idempotency sits inside it.
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(RequestIdMiddleware)
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(  # outermost: preflight is answered before auth/idempotency
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Request-ID",
            "X-Mock-Error",
            "X-Mock-Empty",
        ],
        expose_headers=["X-Request-ID", "Idempotent-Replayed", "Retry-After"],
        max_age=600,
    )
    return app


app = create_app()
