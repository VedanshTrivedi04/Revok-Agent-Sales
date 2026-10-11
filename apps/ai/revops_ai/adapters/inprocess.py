"""In-process ContextProvider and FakeBackend (used by tests, the demo and the eval runner).

FakeBackend mimics what the real backend does with AI output: it re-validates (evidence ids exist,
recipients in allowlist, no tier-3), assigns tiers from the default policy and records everything it was
given, so tests can assert exactly what would reach the database.
"""

from dataclasses import dataclass, field
from typing import Any

from revops_ai.adapters.backend_contract import BackendProposal
from revops_ai.adapters.ports import ProposalsSaved
from revops_ai.domain import Fixture
from revops_ai.llm.schemas import Signal
from revops_ai.tasks.explain import Explanation

DEFAULT_TIER = {"crm_task": 1, "crm_note": 1, "slack_internal": 1, "email_draft": 2, "crm_field_update": 2, "meeting_request": 2}  # fmt: skip
LOCKED_FIELDS = {"amount", "dealstage", "closedate", "pipeline"}


class FixtureProvider:
    def __init__(self, fixtures: list[Fixture], *, strip_signals: bool = True) -> None:
        self.by_account = {f.account.id: f for f in fixtures}
        self.strip = strip_signals

    async def load(self, org_id: str, account_id: str) -> Fixture:
        fx = self.by_account[account_id]
        if not self.strip:
            return fx
        # rules must run on what the model extracted, not on ground truth
        return fx.model_copy(update={"events": [e.model_copy(update={"labeled_signals": []}) for e in fx.events]})  # fmt: skip

    async def finding_id(self, org_id: str, account_id: str) -> str:
        return f"fnd-{account_id}"


@dataclass
class FakeBackend:
    fixtures: dict[str, Fixture] = field(default_factory=dict)
    signals: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    explanations: dict[str, Explanation] = field(default_factory=dict)
    cards: dict[str, dict[str, Any]] = field(default_factory=dict)
    statuses: list[tuple[str, str, dict[str, Any], str | None]] = field(default_factory=list)
    rejections: list[dict[str, Any]] = field(default_factory=list)
    fail_next: int = 0  # simulate backend 5xx for the next N calls

    async def _maybe_fail(self) -> None:
        if self.fail_next > 0:
            self.fail_next -= 1
            raise ConnectionError("backend unavailable")

    async def save_signals(self, org_id: str, event_id: str, signals: list[Signal], model: str, prompt_version: str) -> int:  # fmt: skip
        await self._maybe_fail()
        self.signals[event_id] = [s.model_dump() | {"model": model, "prompt_version": prompt_version} for s in signals]  # fmt: skip
        return len(signals)

    async def save_explanation(self, org_id: str, finding_id: str, ex: Explanation) -> tuple[bool, list[str]]:  # fmt: skip
        await self._maybe_fail()
        errors = [f"unknown evidence id {k}" for c in ex.claims for k in c.evidence_ids if not k.startswith("E")]  # fmt: skip
        if errors:
            return False, errors
        self.explanations[finding_id] = ex
        return True, []

    async def save_proposals(self, org_id: str, finding_id: str, proposals: list[BackendProposal]) -> ProposalsSaved:  # fmt: skip
        await self._maybe_fail()
        out = ProposalsSaved()
        fx = next((f for f in self.fixtures.values() if f"fnd-{f.account.id}" == finding_id), None)
        allowed = {c.email.lower() for c in fx.contacts if c.is_active} if fx else set()
        for p in proposals:
            reason = None
            if p.type == "email_draft" and not set(p.payload["to"] + p.payload["cc"]) <= allowed:
                reason = "recipient_not_allowed"
            if p.type == "crm_field_update" and any(c["field"] in LOCKED_FIELDS for c in p.payload["changes"]):  # fmt: skip
                reason = "tier_blocked"
            if reason:
                out.rejected.append({"type": p.type, "reason": reason})
                self.rejections.append(out.rejected[-1])
                continue
            cid = f"card-{len(self.cards) + 1:03d}"
            tier = DEFAULT_TIER[p.type]
            if "contains_internal_metric" in p.flags:
                tier = max(tier, 2)
            self.cards[cid] = {"type": p.type, "tier": tier, "payload": p.payload, "finding_id": finding_id, "status": "approved" if tier == 1 else "pending_approval"}  # fmt: skip
            out.created_card_ids.append(cid)
            out.tiers[cid] = tier
        return out

    async def run_status(self, org_id: str, run_id: str, status: str, stats: dict[str, Any], error: str | None = None) -> None:  # fmt: skip
        await self._maybe_fail()
        self.statuses.append((run_id, status, stats, error))
