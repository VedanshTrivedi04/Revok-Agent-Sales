from app.connectors.base import Connector
from app.utils.errors import AppError

_REGISTRY: dict[str, Connector] = {}


def register(connector: Connector) -> Connector:
    """Register a connector instance under its `provider` name (one per provider)."""
    _REGISTRY[connector.provider] = connector
    return connector


def get(provider: str) -> Connector:
    try:
        return _REGISTRY[provider]
    except KeyError:
        raise AppError(
            "bad_request", f"No connector registered for provider {provider!r}"
        ) from None


def registered() -> list[str]:
    return sorted(_REGISTRY)


def unregister(provider: str) -> None:
    _REGISTRY.pop(provider, None)
