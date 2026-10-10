"""Endpoint x role permission matrix over the REAL app (backend-plan P1 gate).

For every endpoint guarded by a permission, each of the 5 roles must be refused with 403 exactly
when permissions.py says so; authenticated-any endpoints must never refuse a member; superadmin
endpoints must be invisible (404) to ordinary users. Dependencies run before body validation, so
dummy ids/bodies are enough: we only assert the authorization outcome.
"""

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

import app.routes  # noqa: F401
from app.contract import ENDPOINTS, V1
from app.main import create_app
from app.permissions import Action, has_permission
from tests.helpers import SeededOrg, bearer, mint_jwt
from tests.test_contract import PATH_VALUES

ROLES = ["owner", "admin", "manager", "member", "viewer"]
GUARDED = [d for d in ENDPOINTS if isinstance(d.access, Action)]
ANY = [d for d in ENDPOINTS if d.access == "any" and d.spec.operation_id != "stream"]  # SSE never ends
# Role-guard passes at route level but the service narrows further (org-level provider => admin).
SERVICE_NARROWED = {"connect_integration", "trigger_sync", "disconnect_integration"}
SUPERADMIN = [d for d in ENDPOINTS if d.access == "superadmin"]


def _path(path: str) -> str:
    for k, v in PATH_VALUES.items():
        path = path.replace("{" + k + "}", str(v))
    return path


@pytest.fixture
async def api() -> Any:
    transport = ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        yield c


async def _call(api: AsyncClient, d: Any, org: SeededOrg, role: str) -> int:
    headers = bearer(mint_jwt(org.users[role], org.org_id))
    kwargs: dict[str, Any] = {"headers": headers}
    if d.spec.method in ("POST", "PUT", "PATCH", "DELETE"):
        kwargs["json"] = {}
    r = await api.request(d.spec.method, _path(d.spec.path), **kwargs)
    return r.status_code


def test_matrix_covers_a_meaningful_number_of_endpoints() -> None:
    assert len(GUARDED) >= 40 and len(ANY) >= 15 and len(SUPERADMIN) >= 10


@pytest.mark.parametrize("d", GUARDED, ids=lambda d: d.spec.operation_id)
async def test_permission_guard_matches_the_matrix(
    api: AsyncClient, org_a: SeededOrg, d: Any
) -> None:
    for role in ROLES:
        status = await _call(api, d, org_a, role)
        allowed = has_permission(role, d.access)
        if allowed and d.spec.operation_id in SERVICE_NARROWED:
            continue
        if allowed:
            assert status not in (401, 403), f"{d.spec.operation_id} refused {role} ({status})"
            assert status < 500, f"{d.spec.operation_id} crashed for {role} ({status})"
        else:
            assert status == 403, f"{d.spec.operation_id} let {role} through ({status})"


@pytest.mark.parametrize("d", ANY, ids=lambda d: d.spec.operation_id)
async def test_any_member_endpoints_accept_every_role_and_reject_outsiders(
    api: AsyncClient, org_a: SeededOrg, org_b: SeededOrg, d: Any
) -> None:
    for role in ROLES:
        status = await _call(api, d, org_a, role)
        assert status not in (401, 403), (d.spec.operation_id, role)
        assert status < 500, f"{d.spec.operation_id} crashed for {role} ({status})"
    # a valid user of ANOTHER org presenting a token for org_a is not a member there
    foreign = bearer(mint_jwt(org_b.users["owner"], org_a.org_id))
    r = await api.request(
        d.spec.method,
        _path(d.spec.path),
        headers=foreign,
        json={} if d.spec.method != "GET" else None,
    )
    assert r.status_code == 403
    assert (await api.request(d.spec.method, _path(d.spec.path))).status_code == 401


@pytest.mark.parametrize("d", SUPERADMIN, ids=lambda d: d.spec.operation_id)
async def test_superadmin_endpoints_are_hidden_from_every_org_role(
    api: AsyncClient, org_a: SeededOrg, d: Any
) -> None:
    for role in ROLES:
        assert await _call(api, d, org_a, role) == 404, (d.spec.operation_id, role)


def test_every_prefixed_path_lives_under_api_v1() -> None:
    assert all(d.spec.path.startswith(V1) for d in ENDPOINTS)
