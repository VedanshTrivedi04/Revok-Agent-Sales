import ast
from pathlib import Path

import pytest

from revops_ai.adapters.backend_contract import PAYLOADS, signal_value_dict, to_backend_signal
from revops_ai.evals.heuristic_llm import HeuristicLLM
from revops_ai.evidence.engine import prepare
from revops_ai.fixtures import ROOT, load_all
from revops_ai.llm.schemas import DraftOutput, Signal
from revops_ai.tasks.draft import draft_actions
from revops_ai.tasks.explain import explain_finding
from revops_ai.validation.actions import BANNED, validate_actions

CASES = load_all()
FLAGGED = [(fx, e) for fx, e in CASES if e.finding_type]


async def run(name: str, draft_mode: str = "perfect", **kw):  # type: ignore[no-untyped-def]
    fx, _ = next(c for c in CASES if c[0].case_id == name)
    ri = prepare(fx)
    llm = HeuristicLLM(draft_mode=draft_mode)  # type: ignore[arg-type]
    ex = (await explain_finding(llm, fx, ri)).explanation
    return fx, ri, llm, await draft_actions(llm, fx, ri, ex, **kw)


async def test_acme_gets_four_valid_typed_proposals() -> None:
    fx, ri, _, r = await run("acme_high_risk")
    assert {p.type for p in r.proposals} == {
        "email_draft",
        "crm_task",
        "crm_field_update",
        "slack_internal",
    }
    email = next(p for p in r.proposals if p.type == "email_draft")
    assert email.payload["to"] == ["dana@acme.example.com"] and email.payload["mode"] == "draft"
    assert all(PAYLOADS[p.type].model_validate(p.payload) for p in r.proposals)  # backend-shaped
    field = next(p for p in r.proposals if p.type == "crm_field_update")
    ch = field.payload["changes"][0]
    assert ch == {"object": "company", "id": "hs-acc-acme_high_risk", "field": "health_status", "before": "Green", "after": "At Risk"}  # fmt: skip
    task = next(p for p in r.proposals if p.type == "crm_task")
    assert task.payload["due_date"] == "2026-10-13" and task.payload["owner_crm_id"]
    assert not r.dropped and not r.failed and "contains_internal_metric" not in email.flags


@pytest.mark.parametrize("fx_exp", FLAGGED, ids=[c[0].case_id for c in FLAGGED])
async def test_all_flagged_cases_produce_only_allowlisted_recipients(fx_exp: tuple) -> None:  # type: ignore[type-arg]
    fx, exp = fx_exp
    _, _, _, r = await run(fx.case_id)
    allowed = {c.email.lower() for c in fx.contacts if c.is_active}
    for p in r.proposals:
        if p.type == "email_draft":
            assert set(p.payload["to"] + p.payload["cc"]) <= allowed
            assert not set(p.payload["to"]) & set(exp.forbidden_recipients)
        assert not BANNED.search(str(p.payload))
        assert PAYLOADS[p.type].model_validate(p.payload)


async def test_unknown_recipient_is_dropped() -> None:
    _, _, _, r = await run("acme_high_risk", "bad_recipient")
    assert "email_draft" not in {p.type for p in r.proposals}
    assert any(d["reason"].startswith("recipient_not_in_contacts") for d in r.dropped)


async def test_pricing_language_is_dropped() -> None:
    _, _, _, r = await run("acme_high_risk", "banned")
    assert all("discount" not in str(p.payload).lower() for p in r.proposals)
    assert any("banned_pricing" in d["reason"] for d in r.dropped)


async def test_internal_metric_in_customer_email_is_flagged_not_dropped() -> None:
    _, _, _, r = await run("acme_high_risk", "leak_metric")
    email = next(p for p in r.proposals if p.type == "email_draft")
    assert "contains_internal_metric" in email.flags


async def test_bad_field_value_bad_evidence_placeholder_duplicates() -> None:
    _, _, _, r = await run("acme_high_risk", "bad_field")
    assert any(d["reason"] == "health_value_not_allowed" for d in r.dropped)
    _, _, _, r = await run("acme_high_risk", "bad_evidence")
    assert any(d["reason"].startswith("unknown_evidence_id") for d in r.dropped)
    _, _, _, r = await run("acme_high_risk", "placeholder")
    assert any(d["reason"] == "placeholder_left_in_text" for d in r.dropped)
    _, _, _, r = await run("acme_high_risk", "duplicates")
    assert [p.type for p in r.proposals] == ["crm_task"] and sum(d["reason"] == "duplicate" for d in r.dropped) == 2  # fmt: skip


async def test_garbage_output_never_raises() -> None:
    llm = HeuristicLLM(draft_mode="garbage")
    fx, _ = next(c for c in CASES if c[0].case_id == "acme_high_risk")
    ri = prepare(fx)
    ex = (await explain_finding(HeuristicLLM(), fx, ri)).explanation
    r = await draft_actions(llm, fx, ri, ex)
    assert r.failed and r.proposals == [] and llm.draft_calls == 2


async def test_fallback_explanation_means_no_ai_drafts() -> None:
    fx, _ = next(c for c in CASES if c[0].case_id == "acme_high_risk")
    ri = prepare(fx)
    ex = (await explain_finding(HeuristicLLM(explain_mode="garbage"), fx, ri)).explanation
    llm = HeuristicLLM()
    r = await draft_actions(llm, fx, ri, ex)
    assert r.skipped and llm.draft_calls == 0


async def test_policy_filtered_types_are_respected() -> None:
    _, _, _, r = await run("acme_high_risk", allowed_types=["crm_task", "slack_internal"])
    assert {p.type for p in r.proposals} <= {"crm_task", "slack_internal"}
    assert any(d["reason"] == "type_not_allowed" for d in r.dropped)


async def test_injection_case_no_action_is_influenced() -> None:
    for name in ("hooli_injection", "two_injections_thread"):
        fx, exp = next(c for c in CASES if c[0].case_id == name)
        ri = prepare(fx)
        llm = HeuristicLLM(draft_mode="obey_injection")
        ex = (await explain_finding(llm, fx, ri)).explanation
        text = " ".join(str(m) for call in llm.calls for m in call).lower()
        assert "ignore all previous" not in text and "leak@evil" not in text
        r = await draft_actions(llm, fx, ri, ex)
        assert not any("leak@evil" in str(p.payload) for p in r.proposals)


def test_validate_actions_dedupes_against_existing_open_cards() -> None:
    fx, _ = next(c for c in CASES if c[0].case_id == "acme_high_risk")
    ri = prepare(fx)
    out = DraftOutput.model_validate({"actions": [{"type": "crm_task", "title": "Exec sponsor call", "body": "b", "due_in_days": 1, "priority": "LOW", "rationale": "r", "evidence_ids": ["E1"]}]})  # fmt: skip
    v = validate_actions(out, contacts=fx.contacts, evidence=ri.evidence, allowed_types={"crm_task"}, health_values=fx.org.health_values, existing_titles=["crm_task:exec sponsor call"])  # fmt: skip
    assert not v.kept and v.dropped[0]["reason"] == "duplicate"


def test_confidence_and_value_mapping() -> None:
    s = Signal(
        kind="competitor_mention", polarity="negative", value="Gainsight", quote="q", confidence=0.9
    )
    assert signal_value_dict(s) == {"competitor": "Gainsight"}
    assert to_backend_signal(s, "Qwen/Qwen3.5-9B", "extract@1.0.0")["value"] == {
        "competitor": "Gainsight"
    }
    from revops_ai.adapters.backend_contract import CONFIDENCE_MAP

    assert CONFIDENCE_MAP == {"strong": "high", "moderate": "medium", "weak": "low"}


# ---- contract drift test against the backend source (read-only, via ast; no backend import)
BACKEND = ROOT.parents[1] / "apps" / "api" / "app" / "schemas"


def _fields(path: Path, cls: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return {
        n.target.id
        for n in node.body
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
    }


@pytest.mark.skipif(not BACKEND.exists(), reason="backend sources not present")
def test_payload_mirrors_match_backend_field_names() -> None:
    from revops_ai.adapters import backend_contract as bc

    ap = BACKEND / "action_payloads.py"
    for mine, theirs in [
        (bc.EmailDraftPayload, "EmailDraftPayload"), (bc.CrmTaskPayload, "CrmTaskPayload"),
        (bc.CrmFieldChange, "CrmFieldChange"), (bc.CrmFieldUpdatePayload, "CrmFieldUpdatePayload"),
        (bc.SlackInternalPayload, "SlackInternalPayload"), (bc.CrmRef, "CrmRef"),
    ]:  # fmt: skip
        assert set(mine.model_fields) == _fields(ap, theirs), theirs
    internal = BACKEND / "internal.py"
    assert set(bc.BackendProposal.model_fields) - {"flags"} == _fields(internal, "ProposalIn") | set()  # fmt: skip
    from revops_ai.adapters.backend_contract import signal_value_dict  # noqa: F401

    assert {"kind", "polarity", "value", "confidence", "quote", "model", "prompt_version"} == _fields(internal, "SignalIn")  # fmt: skip


def test_t3_suite_offline() -> None:
    from revops_ai.evals.suites_t3 import t3

    out = t3(live=False)
    assert out["gates"] == {
        "banned_phrases==0": True,
        "recipients==1.0": True,
        "mapped_valid==1.0": True,
    }
