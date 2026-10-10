"""Contract-first routing.

Every public endpoint is declared once with `@endpoint(...)` on a typed stub (path/query/body
models + return annotation = the OpenAPI contract). At app creation `build_router()` wraps each
stub with a dispatcher that picks, per request:

  real handler  - registered with `@real("<operation_id>")` (implemented endpoints)
  mock handler  - when MOCK_API=true (stateful in-memory fixtures, see app/mocks)
  501           - otherwise (endpoint exists in OpenAPI but is not built yet)

REAL_ROUTERS=me,orgs (group names) forces those groups to real code even in mock mode.
`SPECS` also feeds docs/endpoints.md and the contract tests.
"""

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.auth.deps import current_membership, get_claims, require_permission, require_superadmin
from app.config import Settings
from app.permissions import Action
from app.utils.errors import AppError

V1 = "/api/v1"
Access = Action | Literal["any", "user", "public", "api_key", "superadmin"]
Owner = Literal["V", "R"]  # Vedansh (control plane) / Rajwardhan (data & detection plane)


@dataclass(frozen=True)
class Spec:
    method: str
    path: str
    operation_id: str
    group: str
    page: str
    owner: Owner
    phase: int
    access: str
    summary: str


@dataclass
class EndpointDef:
    spec: Spec
    fn: Callable[..., Any]
    status_code: int
    response_class: type[Response] | None
    access: Access


ENDPOINTS: list[EndpointDef] = []
REAL_HANDLERS: dict[str, Callable[..., Awaitable[Any]]] = {}


def endpoint(
    method: str,
    path: str,
    *,
    group: str,
    page: str,
    owner: Owner,
    phase: int,
    access: Access = "any",
    status_code: int = 200,
    response_class: type[Response] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        summary = (inspect.getdoc(fn) or fn.__name__.replace("_", " ")).splitlines()[0]
        spec = Spec(
            method.upper(), V1 + path, fn.__name__, group, page, owner, phase,
            access.value if isinstance(access, Action) else access, summary,
        )  # fmt: skip
        ENDPOINTS.append(EndpointDef(spec, fn, status_code, response_class, access))
        return fn

    return deco


def real(
    operation_id: str,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    def deco(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        REAL_HANDLERS[operation_id] = fn
        return fn

    return deco


def _real_groups(settings: Settings) -> set[str]:
    return {g.strip() for g in settings.real_routers.split(",") if g.strip()}


def resolve_mode(
    group: str, operation_id: str, settings: Settings
) -> Literal["real", "mock", "501"]:
    has_real = operation_id in REAL_HANDLERS
    if settings.mock_api:
        return "real" if has_real and group in _real_groups(settings) else "mock"
    return "real" if has_real else "501"


def _access_dependencies(access: Access, enforce: bool) -> list[Any]:
    if not enforce or access in ("public", "api_key"):
        return []
    if access == "any":
        return [Depends(current_membership)]
    if access == "user":
        return [Depends(get_claims)]
    if access == "superadmin":
        return [Depends(require_superadmin)]
    return [Depends(require_permission(access))]


async def dispatch(opid: str, group: str, request: Request, kwargs: dict[str, Any]) -> Any:
    from app.config import get_settings
    from app.mocks.handlers import serve_mock

    settings = get_settings()
    mode = resolve_mode(group, opid, settings)
    if mode == "real":
        return await REAL_HANDLERS[opid](request, **kwargs)
    if mode == "mock":
        return await serve_mock(opid, request, kwargs)
    raise AppError("not_implemented", f"{opid} is not implemented yet")


def _wrap(defn: EndpointDef) -> Callable[..., Any]:
    sig = inspect.signature(defn.fn)
    request_param = inspect.Parameter("request", inspect.Parameter.KEYWORD_ONLY, annotation=Request)
    opid, group = defn.spec.operation_id, defn.spec.group

    async def wrapper(**kwargs: Any) -> Any:
        request: Request = kwargs.pop("request")
        return await dispatch(opid, group, request, kwargs)

    wrapper.__signature__ = sig.replace(parameters=[*sig.parameters.values(), request_param])  # type: ignore[attr-defined]
    wrapper.__name__ = opid
    wrapper.__doc__ = defn.fn.__doc__
    return wrapper


def build_router(settings: Settings) -> APIRouter:
    import app.routes  # noqa: F401  (imports every route module so ENDPOINTS is populated)

    router = APIRouter()
    enforce = (not settings.mock_api) or settings.mock_auth
    for d in ENDPOINTS:
        extra: dict[str, Any] = {}
        if d.response_class:
            extra["response_class"] = d.response_class
            extra["response_model"] = None
        router.add_api_route(
            d.spec.path,
            _wrap(d),
            methods=[d.spec.method],
            tags=[d.spec.page],
            operation_id=d.spec.operation_id,
            summary=d.spec.summary,
            status_code=d.status_code,
            dependencies=_access_dependencies(d.access, enforce),
            **extra,
        )
    return router
