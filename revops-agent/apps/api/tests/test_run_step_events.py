"""Live agent progress: a run publishes `run.step` events with its real data and persists the same data.

The UI animates the agent workflow from these events (and from the persisted steps afterwards), so
the order, the sequence numbers, the data and the failure path are part of the contract.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db.session import org_session
from app.models.brain import AgentRun, Finding
from app.models.timeline import Account, AccountScoreDay
from app.services import ai_client
from app.services.runs import get_run_service
from app.utils.time import utcnow
from tests.helpers import SeededOrg


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_API", "false")
    get_settings.cache_clear()
    monkeypatch.setattr(ai_client, "enabled", lambda: False)


async def _account(org_id: UUID, **kw: Any) -> UUID:
    acc_id = uuid4()
    async with org_session(org_id) as s:
        s.add(Account(id=acc_id, org_id=org_id, name="Orbit Ltd", domains=["orbit.io"], **kw))
    return acc_id


def _capture(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    from app.workers import tasks_run

    events: list[tuple[str, dict[str, Any]]] = []

    async def fake_publish(org_id: UUID, event_type: str, data: dict[str, Any]) -> None:
        events.append((event_type, data))

    monkeypatch.setattr(tasks_run, "publish", fake_publish)
    return events


async def test_run_publishes_every_step_in_order_with_its_real_data(
    org_a: SeededOrg, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.workers import tasks_run

    org = org_a.org_id
    acc = await _account(org, renewal_date=utcnow().date() + timedelta(days=20), arr=Decimal("84000"), crm_health="Green")  # fmt: skip
    events = _capture(monkeypatch)

    out = await tasks_run.run_account_task.async_fn(None, org, str(acc), "manual", None, None)
    run_id = out["agent_run_id"]

    steps = [d for t, d in events if t == "run.step"]
    expected = [("trigger", "ok")]
    for name in ("context", "rules", "evidence", "scoring", "explain", "findings", "actions"):
        expected += [(name, "started"), (name, "ok")]
    assert [(d["step"], d["status"]) for d in steps] == expected
    assert [d["seq"] for d in steps] == list(range(1, len(expected) + 1))
    assert {d["run_id"] for d in steps} == {run_id} and {d["account_id"] for d in steps} == {str(acc)}  # fmt: skip

    by_step = {d["step"]: d for d in steps if d["status"] == "ok"}
    assert by_step["context"]["data"]["renewal_in_days"] == 20
    assert by_step["context"]["data"]["arr"] == 84000
    rule_keys = {h["rule_key"] for h in by_step["rules"]["data"]["hits"]}
    assert "R04_renewal_near_no_plan" in rule_keys
    assert all(isinstance(h["evidence_refs"], list) for h in by_step["rules"]["data"]["hits"])
    assert by_step["trigger"]["data"] == {"trigger": "manual", "account_name": "Orbit Ltd"}
    risk = next(f for f in by_step["findings"]["data"]["findings"] if f["type"] == "risk")
    assert risk["outcome"] == "created" and risk["finding_id"] and risk["evidence_count"] > 0
    ev = next(i for i in by_step["evidence"]["data"]["items"] if i["type"] == "risk")
    assert ev["count"] == risk["evidence_count"] and ev["contradictions"]
    sc = next(i for i in by_step["scoring"]["data"]["items"] if i["type"] == "risk")
    assert sc["priority_score"] == risk["priority_score"] and sc["confidence"] == risk["confidence"]
    ex = next(i for i in by_step["explain"]["data"]["items"] if i["type"] == "risk")
    assert ex["model"] == "template" and ex["summary"] and ex["claims"] > 0
    # the planner needs contacts to propose anything; the step still reports what exists (none here)
    assert by_step["actions"]["data"] == {"cards": []}

    # the run is announced as final only after it was committed
    assert events[-1] == ("run.updated", {"id": run_id, "account_id": str(acc), "status": "completed"})  # fmt: skip

    # the persisted run carries the same data, so the UI can replay it later
    async with org_session(org) as s:
        detail = await get_run_service(s, org, UUID(run_id))
        finding = (await s.execute(select(Finding).where(Finding.account_id == acc, Finding.type == "risk"))).scalar_one()  # fmt: skip
        scored = (await s.execute(select(AccountScoreDay).where(AccountScoreDay.account_id == acc))).scalar_one()  # fmt: skip
    # the run left today's score behind for "in the last N days" questions
    assert (scored.day, scored.risk_score) == (utcnow().date(), finding.priority_score)
    persisted = {st.name: st for st in detail.steps}
    assert list(persisted) == ["trigger", "context", "rules", "evidence", "scoring", "explain", "findings", "actions"]  # fmt: skip
    assert persisted["context"].data == by_step["context"]["data"]
    assert persisted["rules"].data["hits"] == by_step["rules"]["data"]["hits"]
    assert persisted["findings"].data["findings"][0]["finding_id"] == str(finding.id)
    assert persisted["actions"].data == by_step["actions"]["data"]


async def test_a_failing_step_is_reported_as_failed_and_the_error_still_propagates(
    org_a: SeededOrg, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.workers import tasks_run

    org = org_a.org_id
    acc = await _account(org)
    events = _capture(monkeypatch)

    def boom(_ctx: Any) -> Any:
        raise RuntimeError("rule engine exploded")

    monkeypatch.setattr(tasks_run, "evaluate_rules", boom)

    with pytest.raises(RuntimeError, match="rule engine exploded"):
        await tasks_run.run_account_task.async_fn(None, org, str(acc), "manual", None, None)

    steps = [(d["step"], d["status"]) for t, d in events if t == "run.step"]
    assert steps == [("trigger", "ok"), ("context", "started"), ("context", "ok"), ("rules", "started"), ("rules", "failed")]  # fmt: skip
    failed = [d for t, d in events if t == "run.step" and d["status"] == "failed"][0]
    assert "rule engine exploded" in failed["detail"]
    assert not any(t == "run.updated" for t, _ in events)


async def test_a_debounced_run_is_reported_as_skipped(
    org_a: SeededOrg, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.workers import tasks_run

    org = org_a.org_id
    acc = await _account(org)
    async with org_session(org) as s:
        account = await s.get(Account, acc)
        assert account is not None
        from app.utils.time import utcnow

        account.last_run_at = utcnow()
        run = AgentRun(org_id=org, account_id=acc, trigger="nightly", status="queued")
        s.add(run)
        await s.flush()
        run_id = run.id
    events = _capture(monkeypatch)

    await tasks_run.run_account_task.async_fn(None, org, str(acc), "nightly", None, str(run_id))

    steps = [d for t, d in events if t == "run.step"]
    assert [(d["step"], d["status"]) for d in steps] == [("trigger", "skipped")]
    assert "within the last hour" in steps[0]["detail"]
