"""Generate docs/endpoints.md from the endpoint registry (app/contract.py).

Run: PYTHONPATH=. uv run python scripts/gen_endpoints.py   (a test fails if the file is stale)
Status: `real` = a real handler is registered; `mock` = served only by mock mode (501 otherwise).
"""

from pathlib import Path

from app.contract import ENDPOINTS, REAL_HANDLERS
from app.internal_app import create_internal_app

TARGET = Path(__file__).resolve().parents[3] / "docs" / "endpoints.md"
OWNERS = {"V": "Vedansh", "R": "Rajwardhan"}

HEALTH = [
    ("GET", "/health", "Health", "Vedansh", 0, "real", "public"),
    ("GET", "/health/ready", "Health", "Vedansh", 0, "real", "public"),
]


def render() -> str:
    from app import routes  # noqa: F401  (registers endpoints)

    rows = list(HEALTH)
    for d in ENDPOINTS:
        s = d.spec
        status = "real" if s.operation_id in REAL_HANDLERS else "mock"
        rows.append((s.method, s.path, s.page, OWNERS[s.owner], s.phase, status, s.access))
    lines = [
        "# Endpoints",
        "",
        "> Generated from the endpoint registry (`apps/api/app/contract.py`). Do not edit by hand.",
        "> Regenerate: `cd apps/api && PYTHONPATH=. uv run python scripts/gen_endpoints.py`.",
        "",
        "`Status`: **real** = implemented; **mock** = served by `MOCK_API=true` only (501 `not_implemented` otherwise).",
        "`REAL_ROUTERS=me,orgs` switches those groups to real code even in mock mode.",
        "`Phase` = the phase in which the endpoint becomes real (see `backend-plan.md`).",
        "",
        "| Method | Path | Page | Owner | Phase | Status | Access |",
        "|---|---|---|---|---|---|---|",
    ]
    for m, p, page, owner, phase, status, access in rows:
        lines.append(f"| {m} | `{p}` | {page} | {owner} | P{phase} | {status} | {access} |")
    internal = create_internal_app()
    lines += [
        "",
        "## Internal AI API (`/internal`, own OpenAPI at `/internal/openapi.json`, header `X-Internal-Key`)",
        "",
        "| Method | Path | Owner | Phase | Status |",
        "|---|---|---|---|---|",
    ]
    for route in internal.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", "")
        if methods and path.startswith("/v1/"):
            for m in sorted(methods):
                lines.append(f"| {m} | `/internal{path}` | Vedansh | P6 | mock (501 until V6-02) |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    TARGET.write_text(render(), encoding="utf-8")
    print(f"wrote {TARGET}")
