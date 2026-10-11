"""Planner for Riddhi (the workspace assistant): a typed question becomes one catalog question and its numbers, and
whatever the model returns can never leave the catalog the backend sent."""

import asyncio
from datetime import date
from typing import Any

import httpx
import pytest

from revops_ai.config import Settings
from revops_ai.llm import prompts
from revops_ai.llm.client import FakeLLM
from revops_ai.service import create_service
from revops_ai.tasks.plan import CatalogQuestion, plan_question

TODAY = date(2026, 10, 12)
CATALOG = [
    CatalogQuestion(
        id="high_risk_accounts",
        text="Which accounts have a risk score of 80 or higher?",
        params=["min_score", "limit"],
    ),
    CatalogQuestion(
        id="risk_history",
        text="Which accounts had a risk score of 80 or higher in the last 7 days?",
        params=["days", "min_score", "limit"],
    ),
    CatalogQuestion(id="pending_approvals", text="What is waiting for approval?", params=["limit"]),
]


async def _plan(llm: FakeLLM, question: str = "kitne accounts risk par hain") -> Any:
    return await plan_question(llm, question=question, questions=CATALOG, today=TODAY)


async def test_the_prompt_carries_the_catalog_and_the_question_as_data() -> None:
    llm = FakeLLM([{"question_id": "risk_history", "min_score": 80, "days": 5, "limit": None}])
    r = await _plan(llm, "last 5 days me kitne accounts 80% above risk par hai")
    assert (r.question_id, r.params) == ("risk_history", {"min_score": 80, "days": 5})
    assert r.prompt_version == "plan@" + prompts.available("plan")[-1] and not r.failed

    call = llm.calls[0]
    assert call["task"] == "plan" and call["temperature"] == 0.0
    system, user = (m["content"] for m in call["messages"])
    assert "DATA" in system and "do not follow" in system.lower()
    assert "Today: 2026-10-12" in user
    for q in CATALOG:
        assert f"- {q.id}: {q.text}" in user
    assert "(numbers: days, min_score, limit)" in user
    assert "<question>\nlast 5 days me kitne accounts 80% above risk par hai\n</question>" in user


async def test_none_and_unknown_ids_mean_no_plan() -> None:
    for answer in ("none", "delete_all_accounts", ""):
        r = await _plan(FakeLLM([{"question_id": answer}]))
        assert (r.question_id, r.params, r.failed) == (None, {}, False)


async def test_numbers_the_chosen_question_does_not_take_are_dropped() -> None:
    llm = FakeLLM([{"question_id": "pending_approvals", "min_score": 80, "days": 5, "limit": 3}])
    r = await _plan(llm, "top 3 pending approvals")
    assert (r.question_id, r.params) == ("pending_approvals", {"limit": 3})


async def test_invalid_output_is_retried_once_then_reported_as_failed() -> None:
    ok = FakeLLM(["not json", {"question_id": "high_risk_accounts"}])
    assert (await _plan(ok)).question_id == "high_risk_accounts" and len(ok.calls) == 2

    bad = FakeLLM(["not json", "still not json"])
    r = await _plan(bad)
    assert r.failed and r.question_id is None and len(bad.calls) == 2


async def test_a_slow_or_unreachable_model_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    from revops_ai.tasks import plan as plan_task

    class Slow(FakeLLM):
        async def call_json(self, *a: Any, **k: Any) -> Any:
            self.calls.append({})
            await asyncio.sleep(5)

    class Down(FakeLLM):
        async def call_json(self, *a: Any, **k: Any) -> Any:
            self.calls.append({})
            raise ConnectionError("no route to the model")

    monkeypatch.setattr(plan_task, "BUDGET_S", 0.05)
    slow, down = Slow(), Down()
    assert (await _plan(slow)).failed and len(slow.calls) == 1
    assert (await _plan(down)).failed and len(down.calls) == 1  # the client already retried


async def test_blank_question_or_empty_catalog_never_calls_the_model() -> None:
    llm = FakeLLM()
    assert (await _plan(llm, "   ")).question_id is None
    r = await plan_question(llm, question="at risk?", questions=[], today=TODAY)
    assert r.question_id is None and not r.failed and llm.calls == []


async def test_a_long_question_is_cut_and_whitespace_is_collapsed() -> None:
    llm = FakeLLM([{"question_id": "none"}])
    await _plan(llm, "which   accounts\n\nare " + "risky " * 400)
    user = llm.calls[0]["messages"][1]["content"]
    body = user.split("<question>\n", 1)[1].split("\n</question>", 1)[0]
    assert len(body) == 500 and body.startswith("which accounts are risky")


# ---- the service endpoint
def _service(llm: FakeLLM) -> httpx.AsyncClient:
    cfg = Settings(internal_api_url="http://backend", internal_api_key="k", _env_file=None)  # type: ignore[call-arg]
    app = create_service(llm, client=None, api_key="svc", settings=cfg)  # type: ignore[arg-type]
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://ai", headers={"X-AI-Key": "svc"}
    )


def _body(question: str = "what needs my approval") -> dict[str, Any]:
    return {
        "question": question,
        "today": TODAY.isoformat(),
        "questions": [q.model_dump() for q in CATALOG],
    }


async def test_plan_endpoint_returns_the_plan_with_model_and_prompt_version() -> None:
    svc = _service(FakeLLM([{"question_id": "pending_approvals", "limit": 5}]))
    r = await svc.post("/v1/assistant/plan", json=_body())
    assert r.status_code == 200
    assert r.json() == {
        "question_id": "pending_approvals",
        "params": {"limit": 5},
        "model": "fake",
        "prompt_version": "plan@" + prompts.available("plan")[-1],
    }
    none = _service(FakeLLM([{"question_id": "none"}]))
    assert (await none.post("/v1/assistant/plan", json=_body("lunch?"))).json()[
        "question_id"
    ] is None


async def test_plan_endpoint_needs_the_key_and_reports_a_failed_model_as_503() -> None:
    svc = _service(FakeLLM(["nope", "nope"]))
    assert (await svc.post("/v1/assistant/plan", json=_body())).status_code == 503
    unauth = await svc.post("/v1/assistant/plan", json=_body(), headers={"X-AI-Key": "wrong"})
    assert unauth.status_code == 401


@pytest.mark.parametrize(
    "patch", [{"question": ""}, {"question": "x" * 501}, {"questions": []}, {"today": "soon"}]
)
async def test_plan_endpoint_validates_its_input(patch: dict[str, Any]) -> None:
    svc = _service(FakeLLM())
    assert (await svc.post("/v1/assistant/plan", json={**_body(), **patch})).status_code == 422
