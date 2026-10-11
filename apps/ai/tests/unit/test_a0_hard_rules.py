"""agent.md hard rules enforced on the AI package itself."""

import re
from pathlib import Path

PKG = Path(__file__).parents[2] / "revops_ai"
SRC = {p: p.read_text(encoding="utf-8") for p in PKG.rglob("*.py")}


def test_llm_is_never_given_tools() -> None:
    bad = re.compile(r"\btools\s*=|\bfunctions\s*=|tool_choice|function_call")
    assert not [str(p) for p, t in SRC.items() if bad.search(t) and "client.py" not in p.name]
    client = (PKG / "llm" / "client.py").read_text(encoding="utf-8")
    # the only mentions allowed in the client are in comments/docstrings
    code_lines = [ln for ln in client.splitlines() if not ln.strip().startswith(("#", '"'))]
    assert not [ln for ln in code_lines if re.search(r"tools\s*=|tool_choice\s*=", ln)]


def test_ai_package_never_imports_backend_code() -> None:
    offenders = [str(p) for p, t in SRC.items() if re.search(r"^\s*(from|import)\s+app\b", t, re.M)]
    assert not offenders, offenders


def test_ai_package_has_no_provider_write_clients() -> None:
    banned = ("hubspot", "googleapiclient", "slack_sdk", "smtplib", "gmail")
    offenders = [
        str(p) for p, t in SRC.items()
        if any(re.search(rf"^\s*(from|import)\s+{b}", t, re.M | re.I) for b in banned)
    ]  # fmt: skip
    assert not offenders, offenders


def test_no_external_llm_vendor_sdks() -> None:
    for p, t in SRC.items():
        assert not re.search(
            r"^\s*(from|import)\s+(anthropic|google\.generativeai|cohere)", t, re.M
        ), p
