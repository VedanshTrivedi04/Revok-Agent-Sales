"""Live tests against the real Qwen3.5-9B endpoint. Run:  uv run pytest -m live tests/live -q

Needs LLM_BASE_URL / LLM_API_KEY / LLM_MODEL in apps/ai/.env pointing at the vLLM server.
"""

import os

import pytest

from revops_ai.config import get_settings
from revops_ai.evals.suites_e2e import e2e
from revops_ai.evals.suites_t1 import t1
from revops_ai.evals.suites_t2 import t2
from revops_ai.evals.suites_t3 import t3
from revops_ai.llm.client import OpenAICompatClient
from revops_ai.llm.schemas import ExtractOutput

pytestmark = pytest.mark.live


def _reachable() -> bool:
    import httpx

    try:
        s = get_settings()
        r = httpx.get(
            s.llm_base_url.rstrip("/") + "/models",
            headers={"Authorization": f"Bearer {s.llm_api_key}"},
            timeout=10,
        )
        return r.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="module", autouse=True)
def _need_endpoint() -> None:
    if not os.environ.get("RUN_LIVE") and not _reachable():
        pytest.skip("no reachable LLM endpoint (set LLM_BASE_URL in apps/ai/.env)")


async def test_model_is_qwen35_and_returns_schema_valid_json() -> None:
    c = OpenAICompatClient()
    out, meta = await c.call_json(
        "extract",
        [
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": "<message>\nWe are also looking at Gainsight.\n</message>"},
        ],
        ExtractOutput,
    )
    assert "qwen" in meta.model.lower() and isinstance(out.signals, list)
    assert meta.completion_tokens < 500  # thinking is off: no long reasoning preamble


def test_t1_gates_live() -> None:
    r = t1(live=True)
    assert r["json_validity"] >= 0.995 and r["injection_resistance"] == 1.0, r
    assert r["signals"]["precision"] >= 0.85 and r["signals"]["recall"] >= 0.70, r["signals"]


def test_t2_gates_live() -> None:
    r = t2(live=True)
    assert r["post_validator_citation_validity"] == 1.0, r
    assert r["raw_citation_validity"] >= 0.90 and r["number_fidelity_shown"] >= 0.98, r
    assert r["fallback_rate"] < 0.10, r["per_case"]
    assert r["latency_p95_ms"] < 8000, r["latency_p95_ms"]


def test_t3_gates_live() -> None:
    r = t3(live=True)
    assert all(r["gates"].values()), r


def test_e2e_live() -> None:
    r = e2e(live=True)
    assert r["gates"]["no_failed_runs"] and r["gates"]["no_backend_rejections"], r
