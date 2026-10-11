"""External mode (`AI_MODE=external`): ContextProvider and BackendPort over `/internal/v1`.

In this mode the BACKEND owns rules, evidence numbering, findings and the baseline (template)
explanation and cards. The AI service reads the context of ONE finding (its evidence list, rule hits,
detected contradictions and unknowns) and writes back an explanation and proposals, which the backend
validates again. Our reference engine is not used here (it is the oracle in tests/evals).
"""

import re
from datetime import UTC, date, datetime
from typing import Any

from revops_ai.adapters.backend_contract import BackendProposal, MapCtx
from revops_ai.adapters.internal_client import InternalClient, proposals_body, signals_body
from revops_ai.adapters.ports import ProposalsSaved
from revops_ai.domain import (
    Account,
    Contact,
    Deal,
    Event,
    Evidence,
    Fixture,
    Org,
    RuleHit,
    UsagePoint,
)
from revops_ai.evidence.engine import Ctx, RunInputs, SignalRow
from revops_ai.llm.schemas import Signal
from revops_ai.tasks.explain import TEMPLATE_MODEL, Explanation

EVENT_TYPES = ("email_in", "email_out", "meeting", "note", "call", "deal_stage_change")
EVENT_SOURCES = ("hubspot", "gmail", "gcal", "usage", "system")
# evidence items that only point at a record id: nothing in them for the model (or a claim) to read
_REFERENCE_ONLY = re.compile(r"^Reference ID: ", re.I)
# the backend labels a rule metric "Metric (R01_usage_drop): <sentence>"; the model and the validators
# work on the sentence alone, so rule keys never leak into customer-success prose
_METRIC_PREFIX = re.compile(r"^Metric \([^)]+\):\s*")
_UNKNOWN_TEXT = {
    "renewal_date": "No renewal date is set for this account.",
    "contacts": "No contacts are linked to this account.",
    "usage": "No product usage data connected.",
    "deals": "No deals are linked to this account.",
}
TIER2_TYPES = ("email_draft", "crm_field_update", "meeting_request")


def _dt(v: Any) -> datetime | None:
    if not v:
        return None
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def _empty_ctx(now: datetime, signals: list[SignalRow] | None = None) -> Ctx:
    return Ctx(now, None, None, None, None, False, [], None, None, None, 0, None, [], 0, signals or [], None, None, None, False, False)  # fmt: skip


def _health_values(org: dict[str, Any]) -> dict[str, str]:
    hv = org.get("health_values")
    if isinstance(hv, dict) and hv and all(isinstance(v, str) for v in hv.values()):
        return {str(k): v for k, v in hv.items()}
    return Org().health_values


def fixture_from_context(ctx: dict[str, Any]) -> Fixture:
    a = ctx["account"]
    org = ctx.get("org") or {}
    owner = a.get("owner") or {}
    now = _dt(ctx.get("now")) or datetime.now(UTC)
    renewal = a.get("renewal_date")
    account = Account(
        id=str(a["id"]), name=a.get("name") or "Account", domains=a.get("domains") or [], arr=a.get("arr"),
        plan=a.get("plan_name") or a.get("plan"), seats_purchased=a.get("seats_purchased"),
        renewal_date=date.fromisoformat(renewal) if renewal else None, crm_health=a.get("crm_health"),
        owner_name=owner.get("name") or "Account owner",
        usage_connected=bool(ctx.get("usage")),
    )  # fmt: skip
    contacts = [
        Contact(id=str(c["id"]), name=c.get("name") or c["email"], email=c["email"], title=c.get("title"), role_tags=c.get("role_tags") or [], is_active=c.get("is_active", True))
        for c in ctx.get("contacts", [])
        if c.get("email")
    ]  # fmt: skip
    deals = [
        Deal(
            id=str(d["id"]), name=d.get("name") or "Deal", stage_label=d.get("stage_label") or d.get("stage") or "",
            amount=d.get("amount") or 0, deal_type=d.get("deal_type") if d.get("deal_type") in ("new", "renewal", "expansion") else "other",
            next_step=d.get("next_step"), is_closed=bool(d.get("is_closed", False)),
        )
        for d in ctx.get("deals", [])
    ]  # fmt: skip
    usage = [UsagePoint(period_start=date.fromisoformat(u["period_start"]), active_users=u.get("active_users") or 0, seats_used=u.get("seats_used")) for u in ctx.get("usage", [])]  # fmt: skip
    events = [
        Event(
            id=str(e["id"]),
            source=e.get("source") if e.get("source") in EVENT_SOURCES else "system",
            type=e["type"] if e["type"] in EVENT_TYPES else "note",
            occurred_at=_dt(e["occurred_at"]) or now,
            title=e.get("title"),
            text=e.get("text", ""),
            thread_id=e.get("thread_id"),
        )
        for e in ctx.get("recent_events", [])
    ]
    org_model = Org(
        name=org.get("name") or "our company",
        internal_domain=org.get("primary_domain") or Org().internal_domain,
        health_values=_health_values(org),
    )
    return Fixture(case_id=str(a["id"]), now=now, org=org_model, account=account, contacts=contacts, deals=deals, usage=usage, events=events)  # fmt: skip


def run_inputs_from_context(ctx: dict[str, Any], fx: Fixture) -> RunInputs:
    """The finding as the backend built it. No finding in the context means there is nothing to
    explain (`finding_type=None` ends the run as `no_finding`)."""
    finding = ctx.get("finding")

    def _detail(e: dict[str, Any]) -> str | None:
        # a rule metric's detail is the raw metrics dict: every number users may be shown is already
        # in the label, and unrounded duplicates would let a claim cite a different-looking figure
        if e["kind"] == "rule_metric" or _REFERENCE_ONLY.match(e.get("detail") or ""):
            return None
        return e.get("detail")

    evidence = [
        Evidence(
            key=e["key"],
            kind=e["kind"],
            label=_METRIC_PREFIX.sub("", e["label"]) if e["kind"] == "rule_metric" else e["label"],
            detail=_detail(e),
            source=e.get("source") or "rule",
            source_url=e.get("source_url"),
            occurred_at=_dt(e.get("occurred_at")),
        )
        for e in sorted(ctx.get("evidence", []), key=lambda e: int(str(e["key"])[1:]))
    ]
    by_key = {e.key: e for e in evidence}
    signals = [
        SignalRow(kind=s.get("kind", ""), polarity=s.get("polarity", "neutral"), value=None, quote=s.get("quote") or "", confidence=float(s.get("confidence") or 0), occurred_at=fx.now, event_id="")
        for s in ctx.get("signals", [])
    ]  # fmt: skip
    if not finding:
        return RunInputs(ctx=_empty_ctx(fx.now, signals), hits=[], finding_type=None, severity=None, evidence=evidence, contradictions=[], unknowns=[], missing_sources=[], priority=None, all_hits=[])  # fmt: skip

    hits: list[RuleHit] = []
    for h in ctx.get("rule_hits", []):
        item = by_key.get(str(h.get("evidence_key")))
        if item is None:
            continue
        item.ref_id = (
            f"hit:{h['rule_key']}"  # lets conformance and the fallback find the metric item
        )
        # metrics stay empty on purpose: the backend already wrote every number into the label
        hits.append(RuleHit(rule_key=h["rule_key"], category=h.get("category") or "rule", finding_type=finding["type"], severity_points=int(h.get("severity_points") or 2), human_text=h.get("human_text") or item.label))  # fmt: skip

    contradictions = [
        (c["text"], [k for k in c.get("evidence_ids", []) if k in by_key])
        for c in finding.get("contradictions", [])
        if c.get("text")
    ]
    unknowns = [str(u) for u in finding.get("unknowns", [])] or [
        _UNKNOWN_TEXT[m] for m in ctx.get("missing_data", []) if m in _UNKNOWN_TEXT
    ]
    return RunInputs(
        ctx=_empty_ctx(fx.now, signals), hits=hits, finding_type=finding["type"] if hits else None,
        severity=finding.get("severity"), evidence=evidence, contradictions=contradictions,
        unknowns=unknowns, missing_sources=[], priority=None, all_hits=hits,
    )  # fmt: skip


def map_ctx_from_context(ctx: dict[str, Any], fx: Fixture) -> MapCtx:
    """Real provider ids for the payload mapping. Anything the backend did not give us stays unset,
    and a proposal that needs it is dropped instead of being sent with a made-up id."""
    a, org = ctx["account"], ctx.get("org") or {}
    owner = a.get("owner") or {}
    fields: dict[str, str] = {"revops_risk_level": "revops_risk_level"}
    if org.get("health_property"):
        fields["health"] = str(org["health_property"])
    if org.get("next_step_property"):
        fields["next_step"] = str(org["next_step_property"])
    return MapCtx(
        today=fx.now.date(),
        owner_crm_id=str(owner.get("crm_owner_id") or ""),
        company_crm_id=str(a.get("crm_id") or ""),
        field_property=fields,
        slack_ids={"owner": str(owner["slack_user_id"])} if owner.get("slack_user_id") else {},
        current_values={"health": fx.account.crm_health},
    )


def allowed_types_from_context(ctx: dict[str, Any]) -> list[str]:
    a = ctx["account"]
    owner = a.get("owner") or {}
    # an email is written in the owner's name: without a named owner the template draft stays
    types = ["email_draft"] if owner.get("name") else []
    if a.get("crm_id"):
        types.append("crm_field_update")
        if owner.get("crm_owner_id"):
            types.append("crm_task")
    if owner.get("slack_user_id"):
        types.append("slack_internal")
    return types


class InternalApiProvider:
    """ContextProvider over GET /accounts/{id}/context?finding_id=. The finding id is supplied by
    whoever triggers the run; runs for one account are serialized by the service."""

    extract_in_graph = False  # T1 is driven by the worker over pending-extraction, not per run

    def __init__(self, client: InternalClient, finding_ids: dict[str, str] | None = None) -> None:
        self.client = client
        self.finding_ids = finding_ids if finding_ids is not None else {}
        self.last: dict[str, tuple[Fixture, RunInputs]] = {}
        self.raw: dict[str, dict[str, Any]] = {}

    async def load(self, org_id: str, account_id: str) -> Fixture:
        ctx = await self.client.context(org_id, account_id, self.finding_ids.get(account_id))
        fx = fixture_from_context(ctx)
        self.raw[account_id] = ctx
        self.last[account_id] = (fx, run_inputs_from_context(ctx, fx))
        return fx

    def inputs(self, account_id: str) -> RunInputs:
        return self.last[account_id][1]

    def map_ctx(self, account_id: str) -> MapCtx:
        return map_ctx_from_context(self.raw[account_id], self.last[account_id][0])

    def allowed_types(self, account_id: str) -> list[str]:
        return allowed_types_from_context(self.raw[account_id])

    def forget(self, account_id: str) -> None:
        self.last.pop(account_id, None)
        self.raw.pop(account_id, None)
        self.finding_ids.pop(account_id, None)

    async def finding_id(self, org_id: str, account_id: str) -> str:
        if account_id in self.finding_ids:
            return self.finding_ids[account_id]
        ctx = await self.client.context(org_id, account_id)
        finding = ctx.get("finding") or {}
        return str(finding.get("id") or "")


class InternalApiBackend:
    def __init__(self, client: InternalClient) -> None:
        self.client = client

    async def save_signals(self, org_id: str, event_id: str, signals: list[Signal], model: str, prompt_version: str) -> int:  # fmt: skip
        out = await self.client.save_signals(
            org_id, event_id, signals_body(signals, model, prompt_version)
        )
        return int(out.get("saved", 0))

    async def save_explanation(self, org_id: str, finding_id: str, ex: Explanation) -> tuple[bool, list[str]]:  # fmt: skip
        if ex.model == TEMPLATE_MODEL:
            # our fallback: the backend already shows its own template explanation for this finding
            return True, []
        body = {
            "summary": ex.summary, "claims": [{"text": c.text, "evidence_ids": c.evidence_ids} for c in ex.claims],
            "unknowns": ex.unknowns, "contradictions": [{"text": c.text, "evidence_ids": c.evidence_ids} for c in ex.contradictions],
            "confidence_label": ex.confidence_label, "model": ex.model, "prompt_version": ex.prompt_version,
        }  # fmt: skip
        out = await self.client.save_explanation(org_id, finding_id, body)
        return bool(out.get("accepted")), list(out.get("errors", []))

    async def save_proposals(self, org_id: str, finding_id: str, proposals: list[BackendProposal]) -> ProposalsSaved:  # fmt: skip
        out = await self.client.save_proposals(org_id, finding_id, proposals_body(proposals))
        cards = list(out.get("cards", []))
        if cards:  # the backend reports the tier its policy assigned to each card
            ids = [str(c["card_id"]) for c in cards]
            tiers = {str(c["card_id"]): int(c["tier"]) for c in cards}
        else:  # older backend: assume the default policy (waits for approval)
            ids = [str(i) for i in out.get("created_card_ids", [])]
            tiers = {cid: (2 if proposals[i].type in TIER2_TYPES else 1) for i, cid in enumerate(ids) if i < len(proposals)}  # fmt: skip
        return ProposalsSaved(
            created_card_ids=ids, tiers=tiers, rejected=list(out.get("rejected", []))
        )

    async def run_status(self, org_id: str, run_id: str, status: str, stats: dict[str, Any], error: str | None = None) -> None:  # fmt: skip
        body: dict[str, Any] = {"status": status, "stats": stats, "error": error}
        if stats.get("model"):
            body["model"] = str(stats["model"])
        if stats.get("prompt_versions"):
            body["prompt_versions"] = dict(stats["prompt_versions"])
        await self.client.run_status(org_id, run_id, body)
