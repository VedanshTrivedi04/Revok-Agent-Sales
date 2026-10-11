"""Which third-party apps this deployment has credentials for, and what is still missing.

Used by the connect endpoint (fail early with a clear message instead of sending a user to a
provider with an empty client id) and by `scripts/integration_doctor.py`.
"""

from dataclasses import dataclass

from app.config import Settings

PROVIDER_LABEL = {
    "hubspot": "HubSpot",
    "gmail": "Google",
    "gcal": "Google",
    "slack": "Slack",
}


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    label: str
    missing: list[str]

    @property
    def configured(self) -> bool:
        return not self.missing


def _missing(pairs: dict[str, str]) -> list[str]:
    return [name for name, value in pairs.items() if not value.strip()]


def provider_config(provider: str, s: Settings) -> ProviderConfig:
    """Environment variables still empty for this provider (`[]` means ready)."""
    if provider == "hubspot":
        missing = _missing(
            {
                "HUBSPOT_CLIENT_ID": s.hubspot_client_id,
                "HUBSPOT_CLIENT_SECRET": s.hubspot_client_secret,
            }
        )
    elif provider in ("gmail", "gcal"):
        missing = _missing(
            {"GOOGLE_CLIENT_ID": s.google_client_id, "GOOGLE_CLIENT_SECRET": s.google_client_secret}
        )
    elif provider == "slack":
        missing = _missing(
            {
                "SLACK_CLIENT_ID": s.slack_client_id,
                "SLACK_CLIENT_SECRET": s.slack_client_secret,
                "SLACK_SIGNING_SECRET": s.slack_signing_secret,
            }
        )
    else:
        missing = []
    return ProviderConfig(provider, PROVIDER_LABEL.get(provider, provider), missing)
