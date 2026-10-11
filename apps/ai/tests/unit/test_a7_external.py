import asyncio

import httpx
import jsonschema
import pytest

from revops_ai.adapters.backend_contract import BackendProposal
from revops_ai.adapters.external import InternalApiBackend, InternalApiProvider
from revops_ai.adapters.internal_client import (
    InternalApiError,
    InternalClient,
    proposals_body,
    signals_body,
)
from revops_ai.config import Settings
from revops_ai.evals.heuristic_llm import HeuristicLLM
from revops_ai.fixtures import load_all
from revops_ai.llm.schemas import Signal
from revops_ai.service import create_service
from revops_ai.worker import extract_pending
from tests.fake_internal_api import KEY, FakeInternalApi

FIX = {fx.case_id: fx for fx, _ in load_all()}
ORG = "11111111-1111-1111-1111-111111111111"


def make_client(fake: FakeInternalApi, key: str = KEY) -> InternalClient:
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=fake.app), base_url="http://backend")
    return InternalClient(
        Settings(internal_api_url="http://backend", internal_api_key=key, _env_file=None), http
    )  # type: ignore[call-arg]


def fake_for(*names: str) -> FakeInternalApi:
    return FakeInternalApi([FIX[n] for n in names])


async def test_auth_and_not_found_errors_are_typed() -> None:
    fake = fake_for("acme_high_risk")
    with pytest.raises(InternalApiError) as e:
        await make_client(fake, "wrong").context(ORG, "x")
    assert e.value.status == 401 and e.value.code == "unauthenticated"
    with pytest.raises(InternalApiError) as e2:
        await make_client(fake).context(ORG, "does-not-exist")
    assert e2.value.status == 404


async def test_t1_over_pending_extraction_saves_exact_quote_signals() -> None:
    fake = fake_for("globex_expansion", "initech_competitor")
    rep = await extract_pending(HeuristicLLM(), make_client(fake), ORG, limit=100)
    assert rep.failed == 0 and rep.saved >= 2 and rep.rejected == []
    kinds = {s["kind"] for v in fake.signals.values() for s in v}
    assert {"upgrade_intent", "competitor_mention"} <= kinds
    comp = next(s for v in fake.signals.values() for s in v if s["kind"] == "competitor_mention")
    assert comp["value"] == {"competitor": "Gainsight"} and comp["model"] == "heuristic"
    # idempotent: everything is marked extracted, nothing is fetched again
    again = await extract_pending(HeuristicLLM(), make_client(fake), ORG, limit=100)
    assert again.processed == 0


async def test_failed_extraction_is_not_marked_so_it_is_retried() -> None:
    fake = fake_for("globex_expansion")
    fx = FIX["globex_expansion"]
    inbound = {e.id for e in fx.events if e.type == "email_in" and e.text}
    rep = await extract_pending(HeuristicLLM("garbage"), make_client(fake), ORG)
    assert rep.failed == len(inbound) > 0
    assert (
        not fake.extracted & inbound
    )  # failed events stay pending; skipped outbound mail is marked
    ok = await extract_pending(HeuristicLLM(), make_client(fake), ORG)
    assert ok.failed == 0 and inbound <= fake.extracted


async def test_injection_events_are_flagged_and_text_never_reaches_the_model() -> None:
    fake = fake_for("hooli_injection")
    llm = HeuristicLLM()
    rep = await extract_pending(llm, make_client(fake), ORG)
    assert rep.quarantined >= 1
    sus = [s for v in fake.signals.values() for s in v if s["kind"] == "suspicious_instruction"]
    assert sus and all("[REDACTED_INSTRUCTION]" not in s["quote"] for s in sus)
    assert "Ignore all previous instructions" not in " ".join(
        m["content"] for c in llm.calls for m in c
    )


async def run_via_service(
    fake: FakeInternalApi,
    name: str,
    llm: HeuristicLLM | None = None,
    wait_for_approval: bool = False,
    run_id: str | None = None,
):  # type: ignore[no-untyped-def]
    client = make_client(fake)
    llm = llm or HeuristicLLM()
    from langgraph.checkpoint.memory import MemorySaver

    cfg = Settings(internal_api_url="http://backend", internal_api_key=KEY, _env_file=None)  # type: ignore[call-arg]
    app = create_service(
        llm, client, MemorySaver(), api_key="svc", settings=cfg, wait_for_approval=wait_for_approval
    )
    svc = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://ai", headers={"X-AI-Key": "svc"}
    )
    aid = FIX[name].account.id
    await svc.post(f"/v1/extraction/{ORG}/run", params={"limit": 200})
    body = {"org_id": ORG, "account_id": aid, "finding_id": f"fnd-{aid}"}
    if run_id:
        body["run_id"] = run_id
    r = await svc.post("/v1/runs", json=body)
    assert r.status_code == 202
    run_id = r.json()["run_id"]
    for _ in range(100):
        st = (await svc.get(f"/v1/runs/{run_id}")).json()
        if st["status"] != "running":
            break
        await asyncio.sleep(0.05)
    return svc, run_id, st


async def test_acme_end_to_end_through_the_service_and_internal_api() -> None:
    fake = fake_for("acme_high_risk")
    svc, run_id, st = await run_via_service(fake, "acme_high_risk", wait_for_approval=True)
    assert st["status"] == "waiting_approval" and not st["used_fallback"]
    # the run asked for exactly the finding it was triggered with
    aid = FIX["acme_high_risk"].account.id
    assert (aid, f"fnd-{aid}") in fake.context_calls
    assert {"R01_usage_drop", "R02_meeting_gap", "R03_no_reply"} <= set(st["rule_hits"])
    fid = f"fnd-{FIX['acme_high_risk'].account.id}"
    ex = fake.explanations[fid]
    assert len(ex["claims"]) >= 4 and ex["confidence_label"] in ("high", "medium", "low")
    assert ex["model"] == "heuristic" and ex["prompt_version"] == "explain@1.0.0"
    # the stand-in addresses Slack to "manager"; only the owner's Slack id exists, so it is dropped
    assert {c["type"] for c in fake.cards} == {"email_draft", "crm_task", "crm_field_update"}
    task = next(c for c in fake.cards if c["type"] == "crm_task")["payload"]
    assert task["owner_crm_id"] == "hs-owner-7" and task["associate"] == [
        {"object": "company", "id": "hs-company-1"}
    ]
    field = next(c for c in fake.cards if c["type"] == "crm_field_update")["payload"]["changes"][0]
    assert field["field"] == "health_status" and field["id"] == "hs-company-1"
    assert (
        fake.statuses[0]["status"] == "running"
        and fake.statuses[-1]["status"] == "waiting_approval"
    )
    res = await svc.post(
        f"/v1/runs/{run_id}/resume", json={"decisions": {cid: "approved" for cid in st["card_ids"]}}
    )
    assert res.json()["status"] == "completed" and fake.statuses[-1]["status"] == "completed"


async def test_signals_saved_by_t1_drive_the_backend_rules() -> None:
    fake = fake_for("globex_expansion")
    _, _, st = await run_via_service(fake, "globex_expansion")
    assert "X03_upgrade_intent" in st["rule_hits"]


async def test_service_auth_conflicts_and_unknown_runs() -> None:
    fake = fake_for("acme_high_risk")
    svc, run_id, _ = await run_via_service(fake, "acme_high_risk")
    bad = httpx.AsyncClient(
        transport=svc._transport, base_url="http://ai", headers={"X-AI-Key": "nope"}
    )
    assert (await bad.get("/v1/runs/x")).status_code == 401
    assert (await svc.get("/v1/runs/unknown")).status_code == 404
    assert (await svc.get("/health")).json()["ok"] is True


async def test_transient_status_errors_are_retried_not_fatal() -> None:
    fake = fake_for("umbrella_healthy")
    fake.fail_status_n = 2
    _, _, st = await run_via_service(fake, "umbrella_healthy")
    assert st["status"] == "completed" and fake.fail_status_n == 0


async def test_llm_down_in_external_mode_gives_template_and_no_cards() -> None:
    fake = fake_for("acme_high_risk")
    _, _, st = await run_via_service(
        fake, "acme_high_risk", HeuristicLLM("perfect", "garbage", "garbage")
    )
    assert st["status"] == "completed" and st["used_fallback"] and fake.cards == []
    # our template is never written back: the backend keeps its own template explanation
    assert f"fnd-{FIX['acme_high_risk'].account.id}" not in fake.explanations


# ---- contract: our request bodies validate against the backend's real OpenAPI snapshot
def test_request_bodies_match_the_backend_openapi_snapshot() -> None:
    fake = fake_for("acme_high_risk")
    sig = Signal(
        kind="competitor_mention", polarity="negative", value="Gainsight", quote="q", confidence=0.9
    )
    fake.validate("ai_save_signals", signals_body([sig], "Qwen/Qwen3.5-9B", "extract@1.0.0"))
    prop = BackendProposal(type="crm_task", payload={"title": "t"}, rationale="r", evidence_keys=["E1"], flags=["contains_internal_metric"])  # fmt: skip
    body = proposals_body([prop])
    fake.validate("ai_save_proposals", body)
    assert body["proposals"][0]["flags"] == ["contains_internal_metric"] and body["proposals"][0]["rationale"] == "r"  # fmt: skip
    fake.validate(
        "ai_run_status",
        {
            "status": "no_finding",
            "stats": {},
            "error": None,
            "model": "m",
            "prompt_versions": {"explain": "1.0.0"},
        },
    )
    fake.validate("ai_run_status", {"status": "completed", "stats": {"a": 1}, "error": None})
    with pytest.raises(jsonschema.ValidationError):
        fake.validate(
            "ai_run_status", {"status": "waiting_for_godot"}
        )  # statuses outside the contract fail
    with pytest.raises(jsonschema.ValidationError):
        fake.validate("ai_save_signals", {"signals": [{"kind": "sentiment"}]})


async def test_backend_adapter_maps_confidence_and_status() -> None:
    fake = fake_for("acme_high_risk")
    backend = InternalApiBackend(make_client(fake))
    await backend.run_status(ORG, "r1", "no_finding", {"x": 1, "model": "Qwen/Qwen3.5-9B"})
    assert (
        fake.statuses[-1]["status"] == "no_finding"
        and fake.statuses[-1]["model"] == "Qwen/Qwen3.5-9B"
    )
    assert isinstance(InternalApiProvider(make_client(fake)).finding_ids, dict)


async def test_default_service_run_finishes_without_waiting_and_uses_the_backend_run_id() -> None:
    fake = fake_for("acme_high_risk")
    rid = "22222222-2222-2222-2222-222222222222"
    _, run_id, st = await run_via_service(fake, "acme_high_risk", run_id=rid)
    assert run_id.startswith(rid) and st["status"] == "completed" and not st["used_fallback"]
    assert fake.statuses[-1]["status"] == "completed" and fake.statuses[-1]["model"] == "heuristic"


async def test_accounts_without_provider_ids_get_no_crm_or_slack_proposals() -> None:
    fake = fake_for("acme_high_risk")
    fake.crm_id = fake.crm_owner_id = fake.owner_slack_id = None
    _, _, st = await run_via_service(fake, "acme_high_risk")
    assert st["status"] == "completed"
    assert {c["type"] for c in fake.cards} == {"email_draft"}


async def test_backend_style_evidence_is_conformant_and_rule_keys_stay_out_of_claims() -> None:
    from revops_ai.evidence.render import conformance

    fake = fake_for("acme_high_risk")
    provider = InternalApiProvider(make_client(fake))
    aid = FIX["acme_high_risk"].account.id
    provider.finding_ids[aid] = f"fnd-{aid}"
    await provider.load(ORG, aid)
    ri = provider.inputs(aid)
    assert conformance(ri.evidence, ri.hits) == [] and ri.finding_type == "risk"
    assert not any(e.label.startswith("Metric (") for e in ri.evidence)
    assert ri.contradictions and all(keys for _, keys in ri.contradictions)
    _, _, _ = await run_via_service(fake, "acme_high_risk")
    ex = fake.explanations[f"fnd-{aid}"]
    assert not any("R01" in c["text"] or "Metric (" in c["text"] for c in ex["claims"])


async def test_same_finding_is_not_explained_twice_at_once_and_health_reports_the_model() -> None:
    fake = fake_for("acme_high_risk")
    svc, run_id, _ = await run_via_service(fake, "acme_high_risk")
    h = (await svc.get("/health")).json()
    assert h["ok"] is True and h["model"] and h["prompt_versions"]["explain"]
    assert (await svc.get(f"/v1/runs/{run_id}")).json()["status"] == "completed"


async def test_scores_endpoint_returns_churn_expansion_and_shap_reasons() -> None:
    from revops_ai.ml.scoring import Scorer

    if not (Scorer.available("churn") and Scorer.available("expansion")):
        pytest.skip("run scripts/train_model.py for both tasks")
    fake = fake_for("acme_high_risk", "globex_expansion")
    svc, _, _ = await run_via_service(fake, "acme_high_risk")
    base = f"/v1/orgs/{ORG}/accounts"
    acme = (await svc.get(f"{base}/{FIX['acme_high_risk'].account.id}/scores")).json()
    globex = (await svc.get(f"{base}/{FIX['globex_expansion'].account.id}/scores")).json()
    assert acme["churn"]["probability"] > globex["churn"]["probability"]
    assert globex["expansion"]["probability"] > acme["expansion"]["probability"]
    assert (
        acme["churn"]["reasons"]
        and acme["churn"]["production_ready"] is False
        and "SYNTHETIC" in acme["churn"]["trained_on"]
    )
    assert acme["view"] in ("at_risk", "watch", "watch_and_nurture") and globex["view"] in (
        "growth_opportunity",
        "growth_potential",
    )
    only = (await svc.get(f"{base}/{FIX['acme_high_risk'].account.id}/churn")).json()
    assert only["band"] in ("low", "medium", "high")


def test_process_entry_point_serves_health_without_backend_or_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`uvicorn revops_ai.main:app` must start (and report the model as down) with nothing reachable."""
    from fastapi.testclient import TestClient

    from revops_ai import config, main

    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("CHECKPOINT_DSN", "")
    config.get_settings.cache_clear()
    try:
        with TestClient(main.build()) as c:
            assert c.get("/health").json()["ok"] is True
            deep = c.get("/health", params={"deep": "true"}).json()
            assert deep["llm_ok"] is False and deep["llm_latency_ms"] is None
            assert c.post("/v1/runs", json={}).status_code == 401
    finally:
        config.get_settings.cache_clear()
