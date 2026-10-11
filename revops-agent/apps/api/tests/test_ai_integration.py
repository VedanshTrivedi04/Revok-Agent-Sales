"""AI_MODE=external integration: what the AI service (apps/ai) reads and writes, and how runs hand off.

Covers the contract the AI adapter depends on: a context scoped to ONE finding, extraction that never
re-serves a read event, AI drafts that upgrade the pending template card instead of duplicating it,
AI status reports that never break a finished run, and the run task that triggers the hand-off.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import get_settings
from app.db.session import org_session
from app.models.actions import ActionCard
from app.models.brain import AgentRun, Finding, FindingEvidence, Signal
from app.models.brain import RuleHit as DbRuleHit
from app.models.timeline import Account, Contact, Event
from app.services import ai_client
from app.services.cards import create_from_proposals
from app.utils.time import utcnow
from tests.helpers import SeededOrg


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_API", "false")
    get_settings.cache_clear()


def _h() -> dict[str, str]:
    return {"X-Internal-Key": get_settings().internal_api_key}


async def _account(org_id: UUID, **kw: Any) -> UUID:
    acc_id = uuid4()
    async with org_session(org_id) as s:
        s.add(Account(id=acc_id, org_id=org_id, name=kw.pop("name", "Orbit Ltd"), domains=["orbit.io"], **kw))  # fmt: skip
    return acc_id


async def _finding(org_id: UUID, acc_id: UUID, ftype: str, labels: list[tuple[str, str, str]], **kw: Any) -> UUID:  # fmt: skip
    """labels: (evidence_key, kind, label)."""
    fid = uuid4()
    async with org_session(org_id) as s:
        s.add(
            Finding(
                id=fid,
                org_id=org_id,
                account_id=acc_id,
                type=ftype,
                fingerprint=f"fp-{uuid4()}",
                status="open",
                severity="high",
                priority_score=Decimal("80.0"),
                confidence=0.8,
                title="t",
                model="template",
                prompt_version="template@1",
                **kw,
            )  # fmt: skip
        )
        await s.flush()
        for key, kind, label in labels:
            s.add(FindingEvidence(id=uuid4(), org_id=org_id, finding_id=fid, evidence_key=key, kind=kind, label=label, source="revops", occurred_at=utcnow()))  # fmt: skip
    return fid


async def test_context_is_scoped_to_one_finding_in_numeric_key_order(
    client: AsyncClient, org_a: SeededOrg
) -> None:
    org = org_a.org_id
    acc = await _account(org, external_ids={"hubspot": "9001"}, crm_owner_id="77")
    risk_items = [("E1", "account_field", "Account facts: ARR $84,000")]
    risk_items += [(f"E{i}", "deal", "Supporting deal record") for i in range(3, 12)]
    risk_items.insert(1, ("E2", "rule_metric", "Metric (R01_usage_drop): Active users fell from 52 to 32 (−38.5%) over the last week."))  # fmt: skip
    risk = await _finding(
        org, acc, "risk", risk_items, rule_keys=["R01_usage_drop"],
        unknowns=["No product usage data connected."],
        contradictions=[{"text": "CRM health says 'Green' but rules detected high risk.", "evidence_ids": ["E1"]}],
    )  # fmt: skip
    exp = await _finding(
        org, acc, "expansion",
        [("E1", "account_field", "Account facts: ARR $84,000"), ("E2", "rule_metric", "Metric (X01_seat_saturation): 96% of seats in use.")],
        rule_keys=["X01_seat_saturation"],
    )  # fmt: skip

    base = f"/internal/v1/orgs/{org}/accounts/{acc}/context"
    r = (await client.get(base, params={"finding_id": str(risk)}, headers=_h())).json()
    assert r["finding"]["id"] == str(risk) and r["finding"]["type"] == "risk"
    assert [e["key"] for e in r["evidence"]] == [f"E{i}" for i in range(1, 12)]  # E2 before E10
    assert r["rule_hits"] == [
        {
            "rule_key": "R01_usage_drop",
            "finding_type": "risk",
            "human_text": "Active users fell from 52 to 32 (−38.5%) over the last week.",
            "evidence_key": "E2",
        }
    ]
    assert r["finding"]["contradictions"][0]["evidence_ids"] == ["E1"]
    assert r["finding"]["unknowns"] == ["No product usage data connected."]
    assert r["account"]["crm_id"] == "9001" and r["account"]["owner"]["crm_owner_id"] == "77"
    assert r["org"]["name"] and r["now"]

    e = (await client.get(base, params={"finding_id": str(exp)}, headers=_h())).json()
    assert [x["key"] for x in e["evidence"]] == ["E1", "E2"]
    assert e["rule_hits"][0]["rule_key"] == "X01_seat_saturation"

    # a finding of another account is not served under this account
    other = await _account(org, name="Other")
    res = await client.get(f"/internal/v1/orgs/{org}/accounts/{other}/context", params={"finding_id": str(risk)}, headers=_h())  # fmt: skip
    assert res.status_code == 404


async def test_extraction_marks_every_read_event_and_accepts_quotes_across_line_breaks(
    client: AsyncClient, org_a: SeededOrg
) -> None:
    org = org_a.org_id
    acc = await _account(org)
    quiet, noisy, unmatched, empty = uuid4(), uuid4(), uuid4(), uuid4()
    async with org_session(org) as s:
        for eid, account_id, body in (
            (quiet, acc, "Thanks, see you next week."),
            (noisy, acc, "We are also looking\nat Gainsight for next year."),
            (unmatched, None, "Mail that matched no account."),
            (empty, acc, ""),
        ):
            s.add(Event(id=eid, org_id=org, account_id=account_id, source="gmail", source_record_id=f"m-{eid}", type="email_in", occurred_at=utcnow(), title="Re: plan", body_text=body, raw={}))  # fmt: skip

    url = f"/internal/v1/orgs/{org}/events/pending-extraction"
    page = (await client.get(url, params={"account_id": str(acc)}, headers=_h())).json()
    ids = {e["id"] for e in page["events"]}
    assert ids == {str(quiet), str(noisy)} and page["org_name"]
    assert all(e["account_name"] == "Orbit Ltd" for e in page["events"])

    sig = {"kind": "competitor_mention", "polarity": "negative", "value": {"competitor": "Gainsight"}, "confidence": 0.9, "quote": "looking at Gainsight", "model": "m", "prompt_version": "extract@1"}  # fmt: skip
    out = (await client.post(f"/internal/v1/orgs/{org}/events/{noisy}/signals", json={"signals": [sig]}, headers=_h())).json()  # fmt: skip
    assert out == {"saved": 1, "rejected": []}
    # nothing found is still "read": the event must not be served again
    out = (await client.post(f"/internal/v1/orgs/{org}/events/{quiet}/signals", json={"signals": []}, headers=_h())).json()  # fmt: skip
    assert out["saved"] == 0
    again = (await client.get(url, params={"account_id": str(acc)}, headers=_h())).json()
    assert again["events"] == []

    # a second extraction of the same event replaces its signals instead of doubling them
    await client.post(f"/internal/v1/orgs/{org}/events/{noisy}/signals", json={"signals": [sig]}, headers=_h())  # fmt: skip
    async with org_session(org) as s:
        rows = (await s.execute(select(Signal).where(Signal.event_id == noisy))).scalars().all()
        assert len(rows) == 1 and rows[0].account_id == acc

    res = await client.post(f"/internal/v1/orgs/{org}/events/{unmatched}/signals", json={"signals": []}, headers=_h())  # fmt: skip
    assert res.status_code == 422


async def test_ai_draft_upgrades_the_pending_template_card_and_respects_human_edits(
    client: AsyncClient, org_a: SeededOrg
) -> None:
    org = org_a.org_id
    acc = await _account(org)
    async with org_session(org) as s:
        s.add(Contact(id=uuid4(), org_id=org, account_id=acc, name="Dana Lee", email="dana@orbit.io", is_active=True))  # fmt: skip
    fid = await _finding(org, acc, "risk", [("E1", "account_field", "Account facts")])
    template = {"to": ["dana@orbit.io"], "subject": "Checking in", "body_text": "Hi Dana, checking in.", "mode": "draft"}  # fmt: skip
    async with org_session(org) as s:
        cards = await create_from_proposals(s, org_id=org, account_id=acc, finding_id=fid, proposals=[{"type": "email_draft", "payload": template, "rationale": "template"}])  # fmt: skip
        card_id = cards[0].id

    url = f"/internal/v1/orgs/{org}/findings/{fid}/proposals"
    ai = {"to": ["dana@orbit.io"], "subject": "Time for a quick sync before renewal?", "body_text": "Hi Dana, I would love to hear how the rollout is going.", "mode": "draft"}  # fmt: skip
    body = {"proposals": [{"type": "email_draft", "payload": ai, "rationale": "Re-engage the champion.", "evidence_keys": ["E1", "E99"], "flags": ["contains_internal_metric"]}]}  # fmt: skip
    out = (await client.post(url, json=body, headers=_h())).json()
    assert out["created_card_ids"] == [] and out["rejected"] == []
    assert out["cards"] == [{"card_id": str(card_id), "type": "email_draft", "tier": 2, "status": "pending_approval", "action": "redrafted"}]  # fmt: skip
    async with org_session(org) as s:
        card = await s.get(ActionCard, card_id)
        assert card is not None and card.payload["subject"] == ai["subject"]
        assert card.evidence_keys == ["E1"]  # unknown evidence keys are not stored
        assert "review before sending" in (card.rationale or "")
        assert len((await s.execute(select(ActionCard).where(ActionCard.finding_id == fid))).scalars().all()) == 1  # fmt: skip
        card.edited_payload = {**ai, "subject": "My own subject"}  # a person edited the draft

    out = (await client.post(url, json=body, headers=_h())).json()
    assert out["cards"] == [] and out["rejected"] == [
        {"type": "email_draft", "reason": "duplicate"}
    ]
    async with org_session(org) as s:
        card = await s.get(ActionCard, card_id)
        assert card is not None and card.edited_payload["subject"] == "My own subject"

    # payloads the executor could not run are refused, not turned into cards
    bad = {"proposals": [{"type": "crm_task", "payload": {"title": "Call"}, "rationale": "r"}]}
    out = (await client.post(url, json=bad, headers=_h())).json()
    assert out["cards"] == [] and out["rejected"][0]["reason"].startswith("invalid_payload")
    send = {"proposals": [{"type": "email_draft", "payload": {**ai, "to": ["stranger@else.com"]}, "rationale": "r"}]}  # fmt: skip
    out = (await client.post(url, json=send, headers=_h())).json()
    assert "not in allowlist" in out["rejected"][0]["reason"]


async def test_ai_report_never_breaks_a_finished_run(client: AsyncClient, org_a: SeededOrg) -> None:
    org = org_a.org_id
    run_id = uuid4()
    async with org_session(org) as s:
        s.add(AgentRun(id=run_id, org_id=org, trigger="manual", status="completed", finished_at=utcnow(), stats={"rule_hits_count": 3}))  # fmt: skip
    url = f"/internal/v1/orgs/{org}/runs/{run_id}/status"
    for body in (
        {"status": "running", "stats": {}},
        {"status": "failed", "stats": {"claims": 0}, "error": "explain: APIConnectionError"},
    ):
        assert (await client.post(url, json=body, headers=_h())).status_code == 200
    async with org_session(org) as s:
        run = await s.get(AgentRun, run_id)
        assert run is not None and run.status == "completed" and run.error is None
        assert run.stats["rule_hits_count"] == 3 and run.stats["ai"]["status"] == "failed"

    done = {"status": "completed", "stats": {"claims": 4}, "model": "Qwen/Qwen3.5-9B", "prompt_versions": {"explain": "1.0.0"}}  # fmt: skip
    assert (await client.post(url, json=done, headers=_h())).status_code == 200
    async with org_session(org) as s:
        run = await s.get(AgentRun, run_id)
        assert run is not None and run.status == "completed" and run.model == "Qwen/Qwen3.5-9B"
        assert run.stats["ai"] == {"status": "completed", "claims": 4} and run.stats["rule_hits_count"] == 3  # fmt: skip
        assert run.prompt_versions == {"explain": "1.0.0"}


async def test_ai_explanation_replaces_the_template_and_survives_a_rerun_on_same_evidence(
    client: AsyncClient, org_a: SeededOrg
) -> None:
    org = org_a.org_id
    acc = await _account(org)
    fid = await _finding(org, acc, "risk", [("E1", "account_field", "Account facts"), ("E2", "rule_metric", "Metric (R04_renewal_near_no_plan): Contract renewal in 20 days with no open renewal deal.")], rule_keys=["R04_renewal_near_no_plan"])  # fmt: skip
    url = f"/internal/v1/orgs/{org}/findings/{fid}/explanation"
    body = {"summary": "Renewal is 20 days away and no renewal deal is open.", "claims": [{"text": "Renewal in 20 days with no open renewal deal.", "evidence_ids": ["E2"]}], "model": "Qwen/Qwen3.5-9B", "prompt_version": "explain@1.0.0"}  # fmt: skip
    no_claims = {**body, "claims": []}
    assert (await client.post(url, json=no_claims, headers=_h())).json()["accepted"] is False
    assert (await client.post(url, json=body, headers=_h())).json()["accepted"] is True
    async with org_session(org) as s:
        f = await s.get(Finding, fid)
        assert f is not None and f.model == "Qwen/Qwen3.5-9B"
        assert f.title == "Orbit Ltd: Renewal is 20 days away and no renewal deal is open."


async def test_run_task_runs_with_the_celery_signature_and_hands_findings_to_the_ai(
    org_a: SeededOrg, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`run.account` is called by Celery as fn(session, org_id, *args): it must accept that, commit
    a finding with its template explanation, then ask the AI service to upgrade exactly that finding."""
    from app.workers import tasks_ai, tasks_run

    org = org_a.org_id
    acc = await _account(org, renewal_date=date.today() + timedelta(days=20), arr=Decimal("84000"), crm_health="Green")  # fmt: skip
    extraction: list[dict[str, Any]] = []
    enqueued: list[tuple[str, ...]] = []

    async def fake_extraction(**kw: Any) -> dict[str, Any]:
        extraction.append(kw)
        return {"processed": 0}

    monkeypatch.setattr(ai_client, "enabled", lambda: True)
    monkeypatch.setattr(ai_client, "request_extraction", fake_extraction)
    monkeypatch.setattr(tasks_ai.ai_enhance_task, "delay", lambda *a: enqueued.append(a))
    scored: list[tuple[str, ...]] = []
    monkeypatch.setattr(tasks_ai.ai_scores_task, "delay", lambda *a: scored.append(a))

    out = await tasks_run.run_account_task.async_fn(None, org, str(acc), "manual", None, None)
    assert out["status"] == "completed" and out["ai_requested"] == 1
    assert extraction == [{"org_id": org, "account_id": acc, "limit": 20, "wait": True}]

    async with org_session(org) as s:
        finding = (await s.execute(select(Finding).where(Finding.account_id == acc))).scalar_one()
        assert finding.model == "template" and "R04_renewal_near_no_plan" in finding.rule_keys
        # the detected contradiction (Green health vs risk) is kept and cites its evidence item
        assert finding.contradictions and finding.contradictions[0]["evidence_ids"]
        hits = (await s.execute(select(DbRuleHit).where(DbRuleHit.account_id == acc))).scalars().all()  # fmt: skip
        assert {h.rule_key for h in hits} >= {"R04_renewal_near_no_plan"}
    assert enqueued == [(str(org), str(acc), str(finding.id), out["agent_run_id"], "manual")]
    assert scored == [(str(org), str(acc))]  # every run asks for the account's ML scores

    # contract fixture for apps/ai: a context built by the real rules engine and evidence builder
    if os.environ.get("AI_CONTEXT_FIXTURE"):
        from app.services.internal_ai import get_account_context

        async with org_session(org) as s:
            ctx = await get_account_context(s, org, acc, finding.id)
        Path(os.environ["AI_CONTEXT_FIXTURE"]).write_text(ctx.model_dump_json(indent=1), "utf-8")  # noqa: ASYNC240

    # template mode: same run, nothing is sent anywhere
    monkeypatch.setattr(ai_client, "enabled", lambda: False)
    extraction.clear(), enqueued.clear()
    out = await tasks_run.run_account_task.async_fn(None, org, str(acc), "manual", None, None)
    assert out["ai_requested"] == 0 and extraction == [] and enqueued == []


async def test_llm_health_reports_template_mode_without_inventing_numbers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import admin

    out = await admin.llm_health()
    assert out.mode == "template" and out.status == "not_configured" and out.latency_ms is None

    monkeypatch.setenv("AI_MODE", "external")
    monkeypatch.setenv("AI_SERVICE_URL", "http://127.0.0.1:9")
    get_settings.cache_clear()
    try:
        out = await admin.llm_health()
        assert out.mode == "external" and out.status == "down"
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
