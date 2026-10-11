"""T3 draft_actions: finding + evidence + contacts -> validated, mapped action proposals.

The model proposes typed actions by contact id; code validates (validation/actions.py) and maps them to
the backend payloads (adapters/backend_contract.py). Never raises into the graph.
"""

from dataclasses import dataclass, field

import structlog

from revops_ai.adapters.backend_contract import (  # fmt: skip
    BackendProposal,
    MapCtx,
    MappingError,
    map_ctx_for,
    to_backend_proposal,
)
from revops_ai.domain import Fixture
from revops_ai.evidence.engine import RunInputs
from revops_ai.evidence.render import sanitize_for_prompt
from revops_ai.llm import prompts
from revops_ai.llm.client import CallMeta, LLMClient, LLMOutputError
from revops_ai.llm.schemas import DraftOutput
from revops_ai.tasks.explain import Explanation
from revops_ai.validation.actions import Checked, validate_actions

log = structlog.get_logger()
DEFAULT_ALLOWED = ["email_draft", "crm_task", "crm_field_update", "slack_internal"]


@dataclass
class DraftResult:
    proposals: list[BackendProposal] = field(default_factory=list)
    checked: list[Checked] = field(default_factory=list)
    dropped: list[dict[str, str]] = field(default_factory=list)
    failed: bool = False
    skipped: bool = False
    prompt_version: str = ""
    model: str = ""
    metas: list[CallMeta] = field(default_factory=list)
    first_attempt_actions: int = 0


async def draft_actions(
    llm: LLMClient,
    fx: Fixture,
    ri: RunInputs,
    explanation: Explanation,
    *,
    allowed_types: list[str] | None = None,
    map_ctx: MapCtx | None = None,
    existing_titles: list[str] | None = None,
    prompt_version: str | None = None,
) -> DraftResult:
    p = prompts.load("draft", prompt_version)
    res = DraftResult(prompt_version=p.tag)
    if explanation.needs_review:  # fallback explanation: no AI drafts (aiengineerhandover.md s.6)
        res.skipped = True
        return res
    allowed = allowed_types or DEFAULT_ALLOWED
    thread = next((e for e in sorted(fx.events, key=lambda e: e.occurred_at, reverse=True) if e.thread_id and e.type == "email_in"), None)  # fmt: skip
    ctx = {
        "allowed_types": allowed, "owner_first_name": fx.account.owner_name.split()[0],
        "health_values": list(fx.org.health_values.values()),
        "account": {"name": fx.account.name, "renewal_date": fx.account.renewal_date},
        "owner_name": fx.account.owner_name,
        "finding": {"title": f"{ri.finding_type} finding for {fx.account.name}", "summary": explanation.summary,
                    "claims": [{"text": c.text, "evidence_ids": c.evidence_ids} for c in explanation.claims]},  # fmt: skip
        "evidence": sanitize_for_prompt(ri.evidence),
        "contacts": [c.model_dump() for c in fx.contacts],
        "thread_subject": thread.title if thread else None,
    }  # fmt: skip
    messages = p.render(**ctx)
    out: DraftOutput | None = None
    for attempt in range(2):
        try:
            out, meta = await llm.call_json("draft", messages, DraftOutput, temperature=0.4, max_tokens=1200)  # fmt: skip
            res.metas.append(meta)
            res.model = meta.model
            break
        except LLMOutputError:
            log.warning("draft_invalid_output", attempt=attempt)
    if out is None:
        res.failed = True
        return res
    res.first_attempt_actions = len(out.actions)
    v = validate_actions(
        out, contacts=fx.contacts, evidence=ri.evidence, allowed_types=set(allowed),
        health_values=fx.org.health_values, existing_titles=existing_titles,
        mapped_fields=set(map_ctx.field_property) if map_ctx is not None else None,
    )  # fmt: skip
    res.dropped = v.dropped
    thread_id = thread.thread_id if thread else None
    mctx = map_ctx_for(fx, thread_id) if map_ctx is None else map_ctx
    if mctx.thread_id is None and thread_id:
        mctx = mctx.model_copy(update={"thread_id": thread_id})
    for c in v.kept:
        try:
            res.proposals.append(to_backend_proposal(c, fx.contacts, mctx))
            res.checked.append(c)
        except (MappingError, ValueError) as e:
            res.dropped.append(
                {"type": c.proposal.type, "reason": f"mapping_failed:{type(e).__name__}"}
            )
    return res
