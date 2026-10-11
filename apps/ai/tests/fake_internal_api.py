"""A reference implementation of the backend's /internal/v1 for tests.

It serves ContextOut built with the reference engine (standing in for the backend's rules + evidence
builder), applies the backend's documented validation (quote is a substring of the event text, evidence
ids exist, recipients in the allowlist) and validates EVERY request body against the real backend
contract: apps/api/tests/snapshots/openapi.internal.json.
"""

import json
from pathlib import Path
from typing import Any

import jsonschema
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from revops_ai.domain import Fixture
from revops_ai.evidence.engine import prepare
from revops_ai.validation.quotes import quote_in_text

_ROOT = Path(__file__).resolve().parents[3]
_SNAP_REL = Path("apps") / "api" / "tests" / "snapshots" / "openapi.internal.json"
# the backend lives in revops-agent/ in this repository (apps/api in the original monorepo layout)
SNAP = next(
    (p for p in (_ROOT / "revops-agent" / _SNAP_REL, _ROOT / _SNAP_REL) if p.exists()),
    _ROOT / "revops-agent" / _SNAP_REL,
)
KEY = "test-internal-key"


def _resolve(schema: Any, root: dict[str, Any]) -> Any:
    if isinstance(schema, dict):
        if "$ref" in schema:
            return _resolve(root["components"]["schemas"][schema["$ref"].split("/")[-1]], root)
        return {k: _resolve(v, root) for k, v in schema.items()}
    if isinstance(schema, list):
        return [_resolve(v, root) for v in schema]
    return schema


class FakeInternalApi:
    def __init__(self, fixtures: list[Fixture], strip_signals: bool = True) -> None:
        self.spec = json.loads(SNAP.read_text(encoding="utf-8"))
        self.fixtures = {f.account.id: f for f in fixtures}
        self.strip = strip_signals
        self.signals: dict[str, list[dict[str, Any]]] = {}
        self.explanations: dict[str, dict[str, Any]] = {}
        self.cards: list[dict[str, Any]] = []
        self.statuses: list[dict[str, Any]] = []
        self.requests: list[tuple[str, str, Any]] = []
        self.extracted: set[str] = set()
        self.fail_status_n = 0
        self.context_calls: list[tuple[str, str | None]] = []
        # ids a real backend account may or may not have (None = not synced / not linked)
        self.crm_id: str | None = "hs-company-1"
        self.crm_owner_id: str | None = "hs-owner-7"
        self.owner_slack_id: str | None = "U0REALOWNER"
        self.health_property: str | None = "health_status"
        self.app = self._build()

    def validate(self, opid: str, body: Any) -> None:
        for path in self.spec["paths"].values():
            for op in path.values():
                if op["operationId"] == opid:
                    sch = op["requestBody"]["content"]["application/json"]["schema"]
                    jsonschema.validate(body, _resolve(sch, self.spec))
                    return
        raise AssertionError(f"unknown operation {opid}")

    def _events(self) -> list[dict[str, Any]]:
        out = []
        for fx in self.fixtures.values():
            for e in fx.events:
                if e.id in self.extracted or not e.text.strip():
                    continue
                out.append({"id": e.id, "account_id": fx.account.id, "type": e.type, "occurred_at": e.occurred_at.isoformat(), "title": e.title, "text": e.text, "source": e.source, "thread_id": e.thread_id, "account_name": fx.account.name})  # fmt: skip
        return out

    def _text(self, event_id: str) -> str | None:
        for fx in self.fixtures.values():
            for e in fx.events:
                if e.id == event_id:
                    return e.text
        return None

    def _build(self) -> FastAPI:
        app = FastAPI()
        o = "/v1/orgs/{org}"

        def guard(key: str | None) -> JSONResponse | None:
            if key != KEY:
                return JSONResponse(
                    {"error": {"code": "unauthenticated", "message": "bad key", "details": {}}},
                    status_code=401,
                )
            return None

        @app.get(f"{o}/accounts/{{aid}}/context")
        async def context(org: str, aid: str, finding_id: str | None = None, x_internal_key: str | None = Header(None)) -> Any:  # fmt: skip
            if (r := guard(x_internal_key)) is not None:
                return r
            self.context_calls.append((aid, finding_id))
            fx = self.fixtures.get(aid)
            if fx is None:
                return JSONResponse(
                    {"error": {"code": "not_found", "message": "x", "details": {}}}, status_code=404
                )
            if self.strip:  # rules must see only signals the AI saved
                saved = self.signals
                events = []
                for e in fx.events:
                    from revops_ai.domain import LabeledSignal

                    sigs = [LabeledSignal(kind=s["kind"], polarity=s["polarity"], value=(next(iter(s["value"].values())) if s.get("value") else None), quote=s["quote"], confidence=s["confidence"]) for s in saved.get(e.id, [])]  # fmt: skip
                    events.append(e.model_copy(update={"labeled_signals": sigs}))
                fx = fx.model_copy(update={"events": events})
            ri = prepare(fx)
            metric_key = {h.rule_key: e.key for h in ri.hits for e in ri.evidence if e.ref_id == f"hit:{h.rule_key}"}  # fmt: skip
            metrics = {h.rule_key: h.metrics for h in ri.hits}
            rule_of = {v: k for k, v in metric_key.items()}
            return {
                "now": fx.now.isoformat(),
                "org": {
                    "name": fx.org.name,
                    "primary_domain": fx.org.internal_domain,
                    "extra_domains": [],
                    "health_property": self.health_property,
                    "health_values": fx.org.health_values,
                    "next_step_property": "hs_next_step",
                },
                "finding": None
                if not ri.finding_type
                else {
                    "id": f"fnd-{aid}",
                    "type": ri.finding_type,
                    "severity": ri.severity,
                    "status": "open",
                    "rule_keys": [h.rule_key for h in ri.hits],
                    "unknowns": ri.unknowns,
                    "contradictions": [
                        {"text": t, "evidence_ids": keys} for t, keys in ri.contradictions
                    ],
                    "model": "template",
                    "prompt_version": "template@1",
                },  # fmt: skip
                "account": {
                    "id": fx.account.id,
                    "name": fx.account.name,
                    "arr": fx.account.arr,
                    "plan_name": fx.account.plan,
                    "seats_purchased": fx.account.seats_purchased,
                    "renewal_date": str(fx.account.renewal_date)
                    if fx.account.renewal_date
                    else None,
                    "crm_health": fx.account.crm_health,
                    "domains": fx.account.domains,
                    "crm_id": self.crm_id,
                    "owner": {
                        "name": fx.account.owner_name,
                        "crm_owner_id": self.crm_owner_id,
                        "slack_user_id": self.owner_slack_id,
                    },
                },  # fmt: skip
                "contacts": [c.model_dump(mode="json") for c in fx.contacts],
                "deals": [
                    {
                        "id": d.id,
                        "name": d.name,
                        "stage_label": d.stage_label,
                        "amount": d.amount,
                        "deal_type": d.deal_type,
                        "next_step": d.next_step,
                        "is_closed": d.is_closed,
                    }
                    for d in fx.deals
                ],  # fmt: skip
                "usage": [
                    {
                        "period_start": str(u.period_start),
                        "period_end": str(u.period_start),
                        "active_users": u.active_users,
                        "seats_used": u.seats_used,
                    }
                    for u in fx.usage
                ],  # fmt: skip
                "recent_events": [
                    {
                        "id": e.id,
                        "account_id": fx.account.id,
                        "type": e.type,
                        "occurred_at": e.occurred_at.isoformat(),
                        "title": e.title,
                        "text": e.text,
                        "source": e.source,
                        "thread_id": e.thread_id,
                        "account_name": fx.account.name,
                    }
                    for e in fx.events
                ],  # fmt: skip
                "signals": [],
                # the backend reads a finding's rule hits back from its rule-metric evidence
                "rule_hits": [
                    {
                        "rule_key": h.rule_key,
                        "finding_type": h.finding_type,
                        "human_text": h.human_text,
                        "evidence_key": metric_key[h.rule_key],
                    }
                    for h in ri.hits
                    if h.rule_key in metric_key
                ],  # fmt: skip
                # backend label style: "Metric (<rule key>): <sentence>" with the metrics dict as detail
                "evidence": [
                    {
                        "key": e.key,
                        "kind": e.kind,
                        "label": f"Metric ({rule_of[e.key]}): {e.label}"
                        if e.key in rule_of
                        else e.label,
                        "detail": str(metrics[rule_of[e.key]]) if e.key in rule_of else e.detail,
                        "source": e.source,
                        "source_url": None,
                        "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
                    }
                    for e in ri.evidence
                ],  # fmt: skip
                "missing_data": [] if fx.usage else ["usage"],
            }

        @app.get(f"{o}/events/pending-extraction")
        async def pending(
            org: str,
            limit: int = 25,
            account_id: str | None = None,
            x_internal_key: str | None = Header(None),
        ) -> Any:
            if (r := guard(x_internal_key)) is not None:
                return r
            events = [e for e in self._events() if account_id in (None, e["account_id"])]
            return {"events": events[:limit], "org_name": "Demo SaaS"}

        @app.post(f"{o}/events/{{event_id}}/signals")
        async def save_signals(org: str, event_id: str, request: Request, x_internal_key: str | None = Header(None)) -> Any:  # fmt: skip
            if (r := guard(x_internal_key)) is not None:
                return r
            body = await request.json()
            self.requests.append(("signals", event_id, body))
            self.validate("ai_save_signals", body)
            text = self._text(event_id)
            if text is None:
                return JSONResponse(
                    {"error": {"code": "not_found", "message": "event", "details": {}}},
                    status_code=404,
                )
            ok, rejected = [], []
            for s in body["signals"]:
                (ok if quote_in_text(s["quote"], text) else rejected).append(s)
            self.signals[event_id] = ok
            self.extracted.add(event_id)
            return {
                "saved": len(ok),
                "rejected": [{"kind": s["kind"], "reason": "quote_not_in_text"} for s in rejected],
            }

        @app.post(f"{o}/findings/{{fid}}/explanation")
        async def save_expl(org: str, fid: str, request: Request, x_internal_key: str | None = Header(None)) -> Any:  # fmt: skip
            if (r := guard(x_internal_key)) is not None:
                return r
            body = await request.json()
            self.requests.append(("explanation", fid, body))
            self.validate("ai_save_explanation", body)
            aid = fid.removeprefix("fnd-")
            fx = self.fixtures[aid]
            keys = {e.key for e in prepare(fx).evidence}
            errs = [f"unknown evidence id {k}" for c in body["claims"] + body.get("contradictions", []) for k in c["evidence_ids"] if k not in keys]  # fmt: skip
            if not errs:
                self.explanations[fid] = body
            return {
                "finding_id": "00000000-0000-0000-0000-000000000001",
                "accepted": not errs,
                "errors": errs,
            }

        @app.post(f"{o}/findings/{{fid}}/proposals")
        async def save_props(org: str, fid: str, request: Request, x_internal_key: str | None = Header(None)) -> Any:  # fmt: skip
            if (r := guard(x_internal_key)) is not None:
                return r
            body = await request.json()
            self.requests.append(("proposals", fid, body))
            self.validate("ai_save_proposals", body)
            fx = self.fixtures[fid.removeprefix("fnd-")]
            allowed = {c.email.lower() for c in fx.contacts if c.is_active}
            ids, rejected, cards = [], [], []
            for p in body["proposals"]:
                if (
                    p["type"] == "email_draft"
                    and not set(p["payload"]["to"] + p["payload"].get("cc", [])) <= allowed
                ):
                    rejected.append({"type": p["type"], "reason": "recipient_not_allowed"})
                    continue
                self.cards.append(p)
                cid = f"00000000-0000-0000-0000-{len(self.cards):012d}"
                ids.append(cid)
                tier = 2 if p["type"] in ("email_draft", "crm_field_update") else 1
                cards.append({"card_id": cid, "type": p["type"], "tier": tier, "status": "pending_approval" if tier == 2 else "approved", "action": "created"})  # fmt: skip
            return {"created_card_ids": ids, "cards": cards, "rejected": rejected}

        @app.post(f"{o}/runs/{{run_id}}/status")
        async def status(org: str, run_id: str, request: Request, x_internal_key: str | None = Header(None)) -> Any:  # fmt: skip
            if (r := guard(x_internal_key)) is not None:
                return r
            body = await request.json()
            self.validate("ai_run_status", body)
            if self.fail_status_n > 0:
                self.fail_status_n -= 1
                return JSONResponse(
                    {"error": {"code": "internal_error", "message": "boom", "details": {}}},
                    status_code=503,
                )
            self.statuses.append(body)
            return {"ok": True}

        return app
