"""External AI ports (AI_MODE=external).

Invoked when AI_MODE=external. In production, work is conducted through the
/internal/v1 service-to-service endpoints with X-Internal-Key.
"""

from app.ports.template import ExternalPending
from app.ports.types import (
    ActionProposal,
    EventView,
    ExplainCtx,
    ExplanationOut,
    ExtractCtx,
    PlanCtx,
    SignalIn,
)


class ExternalSignalExtractor(ExternalPending):
    """Signal extractor operating when AI_MODE=external."""

    async def extract(self, ctx: ExtractCtx, event: EventView) -> list[SignalIn]:
        return []


class ExternalExplainer(ExternalPending):
    """Explainer operating when AI_MODE=external."""

    async def explain(self, ctx: ExplainCtx) -> ExplanationOut:
        return ExplanationOut(
            summary=f"External AI explanation for finding {ctx.finding_id}",
            claims=[],
            unknowns=ctx.unknowns,
            contradictions=ctx.contradictions,
            confidence_label="medium",
            model="external-ai",
            prompt_version="external@1",
        )


class ExternalActionPlanner(ExternalPending):
    """Action planner operating when AI_MODE=external."""

    async def plan(self, ctx: PlanCtx) -> list[ActionProposal]:
        return []
