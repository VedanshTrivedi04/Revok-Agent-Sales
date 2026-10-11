import asyncio
import json
import uuid

import pytest

from revops_ai.adapters.inprocess import FakeBackend, FixtureProvider
from revops_ai.evals.heuristic_llm import HeuristicLLM
from revops_ai.fixtures import load_all
from revops_ai.graph.graph import Deps
from revops_ai.graph.runner import AccountRunner, checkpointer
from revops_ai.llm import prompts
from revops_ai.llm.client import CallMeta, LLMOutputError
from revops_ai.observability.tracing import MemorySink, check_alerts, mask
from revops_ai.observability.versions import bucket, select_prompts

CASES = load_all()
FIX = {fx.case_id: fx for fx, _ in CASES}
ORG = "org-demo"


def make(llm=None, *, backend=None, **kw):  # type: ignore[no-untyped-def]
    backend = backend or FakeBackend(fixtures={f.account.id: f for f in FIX.values()})
    sink = MemorySink()
    deps = Deps(
        llm=llm or HeuristicLLM(), provider=FixtureProvider(list(FIX.values())), backend=backend,
        prompts=select_prompts(ORG), sink=sink, **kw,
    )  # fmt: skip
    return deps, backend, sink


async def run_case(name: str, runner_kw=None, **dep_kw):  # type: ignore[no-untyped-def]
    deps, backend, sink = make(**dep_kw)
    async with checkpointer() as saver:
        runner = AccountRunner(deps, saver)
        rid = f"run-{uuid.uuid4().hex[:8]}"
        st = await runner.run(ORG, FIX[name].account.id, rid)
        return runner, deps, backend, sink, rid, st


async def test_acme_full_run_waits_for_approval_then_completes() -> None:
    runner, deps, backend, sink, rid, st = await run_case("acme_high_risk")
    assert st["status"] == "waiting_approval"
    assert st["finding_type"] == "risk" and st["severity"] == "high"
    assert {"R01_usage_drop", "R02_meeting_gap", "R03_no_reply"} <= set(st["rule_hits"])
    assert not st["used_fallback"] and len(st["explanation"]["claims"]) >= 4
    tiers = st["tiers"]
    assert sorted(tiers.values()) == [1, 1, 2, 2]  # task+slack auto, email+field need approval
    pending = [c for c, t in tiers.items() if t == 2]
    assert [s[1] for s in backend.statuses] == ["running", "waiting_approval"]
    done = await runner.resume(rid, {c: "approved" for c in pending})
    assert done["status"] == "completed" and done["decisions"] == {c: "approved" for c in pending}
    assert [s[1] for s in backend.statuses] == ["running", "waiting_approval", "completed"]
    stats = backend.statuses[-1][2]
    assert stats["llm_calls"] >= 3 and stats["cards_created"] == 4 and not stats["fallback"]
    assert set(stats["node_ms"]) >= {"load_context", "extract_signals", "run_rules", "explain", "propose_actions"}  # fmt: skip
    assert [t["meta"].get("partial", False) for t in sink.traces] == [True, False]
    assert done["versions"]["prompts"] == {
        "extract": prompts.available("extract")[-1],
        "explain": "1.0.0",
        "draft": "1.0.0",
    }
    assert done["evidence_hash"]


async def test_signals_extracted_by_t1_feed_the_rules() -> None:
    """Globex has no rule hit from usage alone for upgrade intent: X03 exists only because T1 found it."""
    _, _, backend, _, _, st = await run_case("globex_expansion")
    assert "X03_upgrade_intent" in st["rule_hits"] and st["finding_type"] == "expansion"
    assert any(s and s[0]["kind"] == "upgrade_intent" for s in backend.signals.values())
    # prove the dependency: without extraction (garbage model) the signal rule disappears
    _, _, _, _, _, st2 = await run_case("globex_expansion", llm=HeuristicLLM("garbage"))
    assert "X03_upgrade_intent" not in st2["rule_hits"]


async def test_healthy_account_ends_with_no_finding() -> None:
    _, _, backend, _, _, st = await run_case("umbrella_healthy")
    assert st["status"] == "completed" and st["rule_hits"] == [] and not backend.cards
    assert backend.statuses[-1][2]["result"] == "no_finding"


async def test_injection_is_quarantined_and_influences_nothing() -> None:
    _, deps, backend, sink, _, st = await run_case("two_injections_thread")
    assert st["status"] == "completed" and len(st["quarantined"]) == 2
    seen = " ".join(m["content"] for m in sum(deps.llm.calls, [])).lower()  # type: ignore[attr-defined]
    assert "ignore all previous" not in seen and "leak@evil" not in seen
    assert not any("evil.example.com" in json.dumps(c) for c in backend.cards.values())
    assert not backend.cards  # no rule fired for this account


async def test_llm_down_degrades_to_template_without_cards() -> None:
    _, _, backend, _, _, st = await run_case(
        "acme_high_risk", llm=HeuristicLLM("garbage", "garbage", "garbage")
    )
    assert st["status"] == "completed" and st["used_fallback"]
    assert st["explanation"]["needs_review"] and st["explanation"]["model"] == "template"
    assert backend.cards == {} and backend.statuses[-1][2]["fallback"] is True


async def test_transient_backend_errors_are_retried() -> None:
    backend = FakeBackend(fixtures={f.account.id: f for f in FIX.values()}, fail_next=2)
    _, _, _, _, _, st = await run_case("acme_high_risk", backend=backend)
    assert st["status"] == "waiting_approval" and backend.fail_next == 0


async def test_persistent_backend_outage_fails_cleanly() -> None:
    backend = FakeBackend(fixtures={f.account.id: f for f in FIX.values()}, fail_next=10_000)
    _, _, _, sink, _, st = await run_case("acme_high_risk", backend=backend)
    assert st["status"] == "failed" and "load_context" in st["error"]
    assert sink.traces and sink.traces[0]["meta"]["failed"]


async def test_slow_model_hits_node_timeout_and_fails_cleanly() -> None:
    class Slow(HeuristicLLM):
        async def call_json(self, *a, **k):  # type: ignore[no-untyped-def]
            await asyncio.sleep(0.5)
            return await super().call_json(*a, **k)

    _, _, backend, _, _, st = await run_case("acme_high_risk", llm=Slow(), node_timeout_s=0.1)
    assert st["status"] == "failed" and "extract_signals" in st["error"]
    assert backend.statuses[-1][1] == "failed"


async def test_run_budget_is_enforced() -> None:
    class Slow(HeuristicLLM):
        async def call_json(self, *a, **k):  # type: ignore[no-untyped-def]
            await asyncio.sleep(1)
            return await super().call_json(*a, **k)

    deps, backend, _ = make(llm=Slow())
    async with checkpointer() as saver:
        runner = AccountRunner(deps, saver, budget_s=0.2)
        st = await runner.run(ORG, FIX["acme_high_risk"].account.id, "r-budget")
    assert st["status"] == "failed" and st["error"] == "run budget exceeded"


async def test_rerun_same_run_id_is_idempotent_for_cards() -> None:
    deps, backend, _ = make()
    async with checkpointer() as saver:
        runner = AccountRunner(deps, saver)
        await runner.run(ORG, FIX["acme_high_risk"].account.id, "r-same")
        n = len(backend.cards)
        # resume of an already-finished/waiting thread must not create more cards
        await runner.resume("r-same", {})
        assert len(backend.cards) == n


async def test_backend_rejecting_the_explanation_triggers_template() -> None:
    class Strict(FakeBackend):
        calls = 0

        async def save_explanation(self, org_id, finding_id, ex):  # type: ignore[no-untyped-def]
            Strict.calls += 1
            if Strict.calls == 1:
                return False, ["unknown evidence id E99"]
            return await super().save_explanation(org_id, finding_id, ex)

    backend = Strict(fixtures={f.account.id: f for f in FIX.values()})
    _, _, _, _, _, st = await run_case("acme_high_risk", backend=backend)
    assert (
        st["used_fallback"] and st["stats"]["backend_rejected_explanation"] and backend.cards == {}
    )


# ---------------- observability + versions
def test_masking_and_alerts_and_canary() -> None:
    assert mask({"a": "mail dana@acme.example.com or +1 415 555 0100"}) == {
        "a": "mail [email] or [phone]"
    }
    assert check_alerts([{"fallback": True, "llm_latency_ms": [10]}, {"fallback": False}]) == [
        "fallback_rate_over_20pct"
    ]
    assert check_alerts([{"fallback": False, "llm_latency_ms": [30_000] * 20}]) == [
        "llm_p95_over_20s"
    ]
    assert check_alerts([{"fallback": False, "llm_latency_ms": [100]}]) == []
    assert (
        select_prompts("o1", canary_pct=0, candidate={"explain": "9.9.9"}).versions["explain"]
        == "1.0.0"
    )
    sel = {select_prompts(f"org-{i}", canary_pct=100, candidate={"explain": "1.0.0"}).versions["explain"] for i in range(5)}  # fmt: skip
    assert sel == {"1.0.0"} and bucket("org-1") == bucket("org-1") and 0 <= bucket("x") < 100


async def test_traces_contain_no_customer_text() -> None:
    _, _, _, sink, _, _ = await run_case("acme_high_risk")
    blob = json.dumps(sink.traces)
    assert "dana@acme.example.com" not in blob and "Checking in" not in blob
    assert [s["name"] for s in sink.traces[0]["spans"]][:3] == [
        "load_context",
        "extract_signals",
        "run_rules",
    ]


# ---------------- Postgres checkpoint: survive a worker restart while waiting for approval
def _docker_ok() -> bool:
    try:
        import docker  # type: ignore[import-untyped]

        docker.from_env().ping()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _docker_ok(), reason="docker not available")
async def test_run_survives_worker_restart_while_waiting_for_approval() -> None:
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine", driver=None) as pg:
        dsn = f"postgresql://{pg.username}:{pg.password}@{pg.get_container_host_ip()}:{pg.get_exposed_port(5432)}/{pg.dbname}"  # fmt: skip
        rid = "r-restart"
        deps1, backend1, _ = make()
        async with checkpointer(dsn) as saver:
            r1 = AccountRunner(deps1, saver)
            st = await r1.run(ORG, FIX["acme_high_risk"].account.id, rid)
            assert st["status"] == "waiting_approval"
            pending = [c for c, t in st["tiers"].items() if t == 2]
        # --- "worker restarts": new process objects, empty caches, same database
        deps2, backend2, _ = make(backend=backend1)
        assert deps2.cache == {}
        async with checkpointer(dsn) as saver2:
            r2 = AccountRunner(deps2, saver2)
            st2 = await r2.state(rid)
            assert st2["status"] == "waiting_approval" and st2["card_ids"]
            done = await r2.resume(rid, {c: "rejected" for c in pending})
        assert done["status"] == "completed" and set(done["decisions"].values()) == {"rejected"}
        assert backend1.statuses[-1][1] == "completed"
        assert isinstance(LLMOutputError("x"), Exception) and CallMeta
