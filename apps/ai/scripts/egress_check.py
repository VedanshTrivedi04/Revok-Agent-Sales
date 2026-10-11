"""Privacy check (A8-07): no customer data may go to an external AI API.

    uv run python scripts/egress_check.py

Fails if LLM_BASE_URL points at a known hosted-LLM vendor, if the package contains vendor URLs, or if a
non-private host is used without TLS. A quick-tunnel (trycloudflare) is allowed for demos only and is
reported as a warning because the traffic leaves the private network.
"""

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from revops_ai.config import get_settings  # noqa: E402

VENDORS = ("api.openai.com", "api.anthropic.com", "generativelanguage.googleapis.com", "api.cohere", "api.mistral.ai", "api.groq.com", "openrouter.ai", "api.together.xyz", "api.deepseek.com")  # fmt: skip
DEMO_TUNNELS = ("trycloudflare.com", "ngrok", "loca.lt")


def check_url(url: str) -> tuple[list[str], list[str]]:
    host = urlparse(url).hostname or ""
    errors, warnings = [], []
    if any(v in host for v in VENDORS):
        errors.append(f"{url}: hosted third-party LLM vendor")
    if any(t in host for t in DEMO_TUNNELS):
        warnings.append(f"{url}: public demo tunnel (OK for synthetic data only)")
    private = (
        host in ("localhost", "127.0.0.1")
        or host.startswith(("10.", "192.168.", "172."))
        or host.endswith(".internal")
    )
    if not private and urlparse(url).scheme != "https":
        errors.append(f"{url}: public host without TLS")
    return errors, warnings


def main() -> int:
    s = get_settings()
    errors, warnings = check_url(s.llm_base_url)
    for p in (ROOT / "revops_ai").rglob("*.py"):
        for m in re.finditer(r"https?://[^\s\"')]+", p.read_text(encoding="utf-8")):
            if any(v in m.group(0) for v in VENDORS):
                errors.append(f"{p.relative_to(ROOT)}: vendor URL {m.group(0)}")
    for e in errors:
        print("ERROR", e)
    for w in warnings:
        print("WARN ", w)
    print("egress check:", "FAILED" if errors else "ok")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
