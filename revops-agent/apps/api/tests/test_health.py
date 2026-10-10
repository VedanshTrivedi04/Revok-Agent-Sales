import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.routes import health
from app.utils.errors import AppError


@pytest.fixture
def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t")


async def _ok() -> str:
    return "ok"


async def _down() -> str:
    return "down"


async def test_health_ok(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_ready_ok(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "_check_db", _ok)
    monkeypatch.setattr(health, "_check_redis", _ok)
    r = await client.get("/health/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready", "checks": {"db": "ok", "redis": "ok"}}


async def test_ready_503_when_dependency_down(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(health, "_check_db", _ok)
    monkeypatch.setattr(health, "_check_redis", _down)
    r = await client.get("/health/ready")
    assert r.status_code == 503
    assert r.json()["checks"] == {"db": "ok", "redis": "down"}


async def test_app_error_uses_envelope() -> None:
    app = create_app()

    @app.get("/boom")
    async def boom() -> None:
        raise AppError("card_not_pending", "Card is not pending", 409, {"id": "x"})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/boom")
    assert r.status_code == 409
    assert r.json() == {
        "error": {
            "code": "card_not_pending",
            "message": "Card is not pending",
            "details": {"id": "x"},
        }
    }


async def test_validation_error_uses_envelope() -> None:
    app = create_app()

    @app.get("/needs-int")
    async def needs_int(n: int) -> dict[str, int]:
        return {"n": n}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/needs-int", params={"n": "abc"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
