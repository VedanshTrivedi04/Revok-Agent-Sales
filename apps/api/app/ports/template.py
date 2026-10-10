"""Default (AI_MODE=template) implementations. Signatures are final; bodies land in Phase 3."""

from app.ports.types import (
    ActionProposal,
    EventView,
    ExplainCtx,
    ExplanationOut,
    ExtractCtx,
    PlanCtx,
    SignalIn,
)


class NullSignalExtractor:
    """No signals: rules R06/R07/R11/X03 stay quiet until an AI extractor is plugged in."""

    async def extract(self, ctx: ExtractCtx, event: EventView) -> list[SignalIn]:
        return []


class TemplateExplainer:
    """Rule-text based explanation with exact numbers and evidence ids (R3-xx, Phase 3)."""

    model = "template"
    prompt_version = "template@1"

    async def explain(self, ctx: ExplainCtx) -> ExplanationOut:
        raise NotImplementedError("TemplateExplainer body is built in Phase 3 (R3 rules texts)")


class TemplateActionPlanner:
    """Fixed per-rule mapping to cards (backend-plan.md section 2.3), built in Phase 3."""

    async def plan(self, ctx: PlanCtx) -> list[ActionProposal]:
        raise NotImplementedError("TemplateActionPlanner body is built in Phase 3 (V3-05)")


class ExternalPending:
    """AI_MODE=external: work is done by the external AI service through /internal/v1 (Phase 6).

    Until then calling these ports is a configuration error, not a silent no-op.
    """

    async def extract(self, ctx: ExtractCtx, event: EventView) -> list[SignalIn]:
        raise NotImplementedError("AI_MODE=external: signals arrive via /internal/v1 (Phase 6)")

    async def explain(self, ctx: ExplainCtx) -> ExplanationOut:
        raise NotImplementedError(
            "AI_MODE=external: explanations arrive via /internal/v1 (Phase 6)"
        )

    async def plan(self, ctx: PlanCtx) -> list[ActionProposal]:
        raise NotImplementedError("AI_MODE=external: proposals arrive via /internal/v1 (Phase 6)")
