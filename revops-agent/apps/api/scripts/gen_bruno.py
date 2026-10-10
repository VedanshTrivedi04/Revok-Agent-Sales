"""Generate a Bruno API collection (./bruno) from the endpoint registry.

Run: PYTHONPATH=. uv run python scripts/gen_bruno.py
Open the `bruno/` folder in Bruno, pick the `local` or `staging` environment, set `token`
(`uv run python scripts/mint_jwt.py manager`), and every endpoint is one click away.
"""

import json
import re
import shutil
from pathlib import Path
from typing import Any

from app import routes  # noqa: F401
from app.contract import ENDPOINTS
from app.mocks import data as D

OUT = Path(__file__).resolve().parents[3] / "bruno"

PATH_VALUES: dict[str, str] = {
    "account_id": D.ACC["acme"], "finding_id": D.FINDING_IDS["acme"], "card_id": D.CARD_IDS["acme_email"],
    "member_id": D.uid("membership:member"), "invite_id": D.uid("invite:1"), "key_id": D.uid("key:1"),
    "integration_id": D.uid("integration:hubspot"), "provider": "hubspot", "job_id": D.uid("job:1"),
    "org_id": D.ORG_ID, "entry_id": "4", "run_id": D.uid("run:0"), "key": "R01_usage_drop",
    "action_type": "email_draft", "review_id": D.uid("review:1"),
}  # fmt: skip

BODIES: dict[str, Any] = {
    "patch_me": {"name": "Priya M"}, "create_org": {"name": "New Co"},
    "patch_current_org": {"name": "Demo SaaS Inc"}, "delete_current_org": {"confirm": "Demo SaaS"},
    "patch_member": {"role": "manager"}, "create_invite": {"email": "new@demo-saas.example.com", "role": "member"},
    "accept_invite": {"token": "token-from-email"}, "put_field_mapping": {"arr_property": "annualrevenue"},
    "ingest_usage": [{"account_key": "acme.example.com", "account_key_type": "domain", "period_start": "2026-10-05", "granularity": "week", "active_users": 30}],
    "create_api_key": {"name": "Usage pipeline"}, "patch_account": {"add_domains": ["acme.io"]},
    "dismiss_finding": {"reason": "not_relevant"}, "snooze_finding": {"until": "2026-11-01T00:00:00Z"},
    "finding_feedback": {"useful": True}, "patch_card": {"edited_payload": D.EMAIL}, "approve_card": {},
    "reject_card": {"reason": "not_now"}, "assign_card": {"user_id": D.USER_IDS["manager"]},
    "export_log": {"format": "csv"}, "put_rule": {"enabled": True, "params": {"drop_pct": 25}},
    "preview_rule": {"params": {"drop_pct": 20}}, "put_autonomy": {"tier": 2},
    "resolve_entity_review": {"ignore": True}, "mark_notifications_read": {"all": True},
    "run_evals": {"suite": "smoke"}, "put_flag": {"key": "email_send", "default": True},
    "slack_events": {"type": "url_verification", "challenge": "abc"}, "slack_interactions": {"type": "block_actions"},
}  # fmt: skip

PUBLIC = {"public", "api_key"}


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", " ", s).strip()


def render() -> dict[str, str]:
    files: dict[str, str] = {
        "bruno.json": json.dumps({"version": "1", "name": "RevOps Agent API", "type": "collection"}, indent=2) + "\n",
        "environments/local.bru": "vars {\n  baseUrl: http://localhost:8000\n  token: PASTE_JWT_HERE\n}\n",
        "environments/staging.bru": "vars {\n  baseUrl: https://api-staging.example.com\n  token: PASTE_JWT_HERE\n}\n",
    }  # fmt: skip
    seq: dict[str, int] = {}
    for d in ENDPOINTS:
        s = d.spec
        folder = slug(s.page)
        seq[folder] = seq.get(folder, 0) + 1
        method = s.method.lower()
        body = BODIES.get(s.operation_id)
        url = s.path
        for k, v in PATH_VALUES.items():
            url = url.replace("{" + k + "}", v)
        lines = [
            "meta {", f"  name: {s.operation_id}", "  type: http", f"  seq: {seq[folder]}", "}", "",
            f"{method} {{", f"  url: {{{{baseUrl}}}}{url}", f"  body: {'json' if body is not None else 'none'}",
            "  auth: bearer" if s.access not in PUBLIC else "  auth: none", "}", "",
        ]  # fmt: skip
        if s.access not in PUBLIC:
            lines += ["auth:bearer {", "  token: {{token}}", "}", ""]
        if s.access == "api_key":
            lines += ["auth:bearer {", "  token: rk_live_PASTE_API_KEY", "}", ""]
        if body is not None:
            lines += [
                "body:json {",
                *("  " + ln for ln in json.dumps(body, indent=2).splitlines()),
                "}",
                "",
            ]
        lines += [
            "docs {",
            f"  {s.summary}",
            f"  Page: {s.page} | Owner: {s.owner} | Phase: P{s.phase} | Access: {s.access}",
            "}",
            "",
        ]
        files[f"{folder}/{s.operation_id}.bru"] = "\n".join(lines)
    return files


if __name__ == "__main__":
    if OUT.exists():
        shutil.rmtree(OUT)
    for rel, content in render().items():
        p = OUT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    print(f"wrote {len(render())} files to {OUT}")
