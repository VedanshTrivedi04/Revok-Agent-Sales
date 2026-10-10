"""Generate docs/error-codes.md from app.utils.errors.ERROR_CODES.

Run: uv run python scripts/gen_error_codes.py   (a test fails if the file is stale)
"""

from pathlib import Path

from app.utils.errors import ERROR_CODES

TARGET = Path(__file__).resolve().parents[3] / "docs" / "error-codes.md"


def render() -> str:
    lines = [
        "# Error codes",
        "",
        "> Generated from `apps/api/app/utils/errors.py` (`ERROR_CODES`). Do not edit by hand.",
        "",
        'Every error uses the envelope `{"error": {"code", "message", "details"}}`. '
        "Foreign-tenant ids return `404 not_found`, never 403.",
        "",
        "| Code | HTTP | Meaning |",
        "|---|---|---|",
    ]
    for code, (status, meaning) in sorted(ERROR_CODES.items(), key=lambda kv: (kv[1][0], kv[0])):
        lines.append(f"| `{code}` | {status} | {meaning} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    TARGET.write_text(render(), encoding="utf-8")
    print(f"wrote {TARGET}")
