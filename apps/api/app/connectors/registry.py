from app.connectors.base import Connector
from app.utils.errors import AppError

_REGISTRY: dict[str, Connector] = {}


def register(connector: Connector) -> Connector:
    """Register a connector instance under its `provider` name (one per provider)."""
    _REGISTRY[connector.provider] = connector
    return connector


def get(provider: str) -> Connector:
    if provider in _REGISTRY:
        return _REGISTRY[provider]

    # Lazy-register default connectors
    if provider == "hubspot":
        from app.connectors.hubspot.client import HubSpotConnector

        c = HubSpotConnector()
        register(c)
        return c
    if provider == "gmail":
        from app.connectors.google.client import GmailConnector

        gc = GmailConnector()
        register(gc)
        return gc
    if provider == "gcal":
        from app.connectors.google.client import GCalConnector

        gc_cal = GCalConnector()
        register(gc_cal)
        return gc_cal

    raise AppError("bad_request", f"No connector registered for provider {provider!r}")


def registered() -> list[str]:
    return sorted(_REGISTRY)


def unregister(provider: str) -> None:
    _REGISTRY.pop(provider, None)
