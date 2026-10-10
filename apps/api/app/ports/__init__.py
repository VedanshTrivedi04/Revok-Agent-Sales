"""AI ports: the only seam through which AI plugs into the backend.

Defaults (AI_MODE=template) are deterministic: NullSignalExtractor, TemplateExplainer,
TemplateActionPlanner (bodies arrive in Phase 3). The AI engineer later swaps an implementation or
calls /internal/v1; no backend refactor is needed. AI output NEVER bypasses backend validation
(evidence ids, recipient allowlist, tier policy, banned phrases).
"""

from typing import Protocol, runtime_checkable

from app.ports.types import (
    ActionProposal,
    EventView,
    ExplainCtx,
    ExplanationOut,
    ExtractCtx,
    PlanCtx,
    SignalIn,
)


@runtime_checkable
class SignalExtractor(Protocol):
    async def extract(self, ctx: ExtractCtx, event: EventView) -> list[SignalIn]: ...


@runtime_checkable
class Explainer(Protocol):
    async def explain(self, ctx: ExplainCtx) -> ExplanationOut: ...


@runtime_checkable
class ActionPlanner(Protocol):
    async def plan(self, ctx: PlanCtx) -> list[ActionProposal]: ...


__all__ = [
    "ActionPlanner", "ActionProposal", "EventView", "ExplainCtx", "Explainer", "ExplanationOut",
    "ExtractCtx", "PlanCtx", "SignalExtractor", "SignalIn",
]  # fmt: skip
