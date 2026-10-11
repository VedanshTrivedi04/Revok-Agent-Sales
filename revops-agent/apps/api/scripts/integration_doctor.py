"""Integration doctor: is this deployment ready to connect HubSpot, Google and Slack?

Reads the same settings the API reads and prints, per provider, what is missing and the exact
redirect / webhook URLs to register in that provider's developer console. It makes no network
calls and changes nothing.

    uv run python scripts/integration_doctor.py                 # everything
    uv run python scripts/integration_doctor.py --only hubspot  # one provider
    uv run python scripts/integration_doctor.py --connections   # also list connections in the DB

Exit code 1 when a selected provider is not ready, so it can gate a deploy.
"""

import argparse
import asyncio
import base64
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import DEV_INTERNAL_KEY, DEV_JWT_SECRET, LOCAL_ENVS, Settings, get_settings  # noqa: E402
from app.services.integration_config import provider_config  # noqa: E402

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


@dataclass(frozen=True)
class Check:
    level: str
    area: str
    message: str


def _is_local(url: str) -> bool:
    return (urlparse(url).hostname or "") in {"localhost", "127.0.0.1", "::1"}


def _valid_enc_keys(raw: str) -> bool:
    """`id:base64(32 bytes)` entries separated by commas (first one is the active key)."""
    for entry in [e.strip() for e in raw.split(",") if e.strip()]:
        key_id, _, b64 = entry.partition(":")
        if not key_id or not b64:
            return False
        try:
            if len(base64.b64decode(b64, validate=True)) != 32:
                return False
        except ValueError:
            return False
    return bool(raw.strip())


def redirect_uris(s: Settings) -> dict[str, list[str]]:
    base = s.public_api_url.rstrip("/")
    return {
        "hubspot": [f"{base}/api/v1/oauth/hubspot/callback"],
        "google": [f"{base}/api/v1/oauth/gmail/callback", f"{base}/api/v1/oauth/gcal/callback"],
        "slack": [f"{base}/api/v1/slack/oauth/callback"],
    }


def run_checks(s: Settings, only: set[str] | None = None) -> list[Check]:
    def want(name: str) -> bool:
        return only is None or name in only

    out: list[Check] = []

    # --- platform basics (needed by every integration)
    local = s.app_env in LOCAL_ENVS
    out.append(
        Check(
            PASS
            if s.api_jwt_secret != DEV_JWT_SECRET and len(s.api_jwt_secret) >= 32
            else (WARN if local else FAIL),
            "platform",
            "API_JWT_SECRET is a unique 32+ character value (shared with the web app)",
        )
    )
    out.append(
        Check(
            PASS if _valid_enc_keys(s.token_enc_keys) else (WARN if local else FAIL),
            "platform",
            "TOKEN_ENC_KEYS is set (id:base64 of 32 bytes); provider tokens are encrypted with it",
        )
    )
    out.append(
        Check(
            PASS
            if s.internal_api_key != DEV_INTERNAL_KEY and len(s.internal_api_key) >= 16
            else (WARN if local else FAIL),
            "platform",
            "INTERNAL_API_KEY is unique (protects /internal/v1 for the AI service)",
        )
    )
    origins = {o.strip().rstrip("/") for o in s.cors_origins.split(",") if o.strip()}
    out.append(
        Check(
            PASS if s.web_url.rstrip("/") in origins else WARN,
            "platform",
            f"CORS_ORIGINS includes WEB_URL ({s.web_url})",
        )
    )
    out.append(
        Check(
            WARN if s.mock_api else PASS,
            "platform",
            "MOCK_API is off (real handlers, not canned responses)"
            if not s.mock_api
            else "MOCK_API is on: connectors are not used",
        )
    )

    # --- per provider
    for name, providers in (("hubspot", ["hubspot"]), ("google", ["gmail"]), ("slack", ["slack"])):
        if not want(name):
            continue
        cfg = provider_config(providers[0], s)
        if cfg.configured:
            out.append(Check(PASS, name, "client credentials are set"))
        else:
            out.append(
                Check(FAIL, name, "missing environment variables: " + ", ".join(cfg.missing))
            )
        for uri in redirect_uris(s)[name]:
            out.append(
                Check(PASS if cfg.configured else WARN, name, f"register this redirect URL: {uri}")
            )

    if want("slack"):
        base = s.public_api_url.rstrip("/")
        if _is_local(base) or not base.startswith("https://"):
            out.append(
                Check(
                    FAIL if not local else WARN,
                    "slack",
                    "Slack needs a public HTTPS PUBLIC_API_URL for redirects, events and buttons (use a tunnel such as ngrok or cloudflared while developing)",
                )
            )
        else:
            out.append(Check(PASS, "slack", "PUBLIC_API_URL is public HTTPS"))
        out.append(Check(PASS, "slack", f"Event Subscriptions URL: {base}/api/v1/slack/events"))
        out.append(Check(PASS, "slack", f"Interactivity URL: {base}/api/v1/slack/interactions"))

    if (
        want("hubspot")
        and not _is_local(s.public_api_url)
        and not s.public_api_url.startswith("https://")
    ):
        out.append(
            Check(FAIL, "hubspot", "HubSpot redirect URLs must be HTTPS unless they are localhost")
        )
    if want("google"):
        out.append(
            Check(
                WARN,
                "google",
                "pilots: add each user as a Test user on the consent screen; public launch needs Google verification + CASA (docs/go-live.md)",
            )
        )
    return out


async def list_connections() -> list[str]:
    from sqlalchemy import select

    from app.db.session import admin_session
    from app.models.integrations import Integration

    lines: list[str] = []
    async with admin_session() as s:
        rows = (
            (await s.execute(select(Integration).order_by(Integration.created_at))).scalars().all()
        )
        for i in rows:
            lines.append(
                f"{str(i.org_id)[:8]}  {i.provider:<9} {i.scope_level:<5} {i.status:<13} "
                f"last_success={i.last_success_at}  error={i.last_error or '-'}"
            )
    return lines or ["(no connections yet)"]


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--only", choices=["hubspot", "google", "slack"], action="append")
    ap.add_argument(
        "--connections", action="store_true", help="list connections stored in the database"
    )
    args = ap.parse_args()

    s = get_settings()
    checks = run_checks(s, set(args.only) if args.only else None)
    print(
        f"Integration doctor (APP_ENV={s.app_env}, PUBLIC_API_URL={s.public_api_url}, WEB_URL={s.web_url})\n"
    )
    area = ""
    for c in checks:
        if c.area != area:
            area = c.area
            print(f"[{area}]")
        print(f"  {c.level:<4} {c.message}")
    if args.connections:
        print("\n[connections]")
        for line in asyncio.run(list_connections()):
            print("  " + line)

    failed = [c for c in checks if c.level == FAIL]
    print(
        f"\n{'NOT READY' if failed else 'READY'}: {len(failed)} blocking, {sum(c.level == WARN for c in checks)} warnings"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
