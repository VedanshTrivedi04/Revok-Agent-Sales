"""Per-account run state (aiengineerhandover.md section 4.1). Everything here is JSON-serializable so it
can be checkpointed in Postgres; heavy objects (fixture, evidence) are rebuilt deterministically."""

from typing import Any, TypedDict


class RunState(TypedDict, total=False):
    org_id: str
    account_id: str
    run_id: str
    trigger: str
    finding_id: str
    signals: dict[str, list[dict[str, Any]]]  # event_id -> validated signals (exact quotes)
    quarantined: list[str]  # event ids that contained instruction-like text
    rule_hits: list[str]
    finding_type: str | None
    severity: str | None
    priority: float | None
    evidence_hash: str
    explanation: dict[str, Any] | None
    used_fallback: bool
    proposals: list[dict[str, Any]]
    dropped_actions: list[dict[str, str]]
    card_ids: list[str]
    tiers: dict[str, int]
    rejected: list[dict[str, Any]]
    decisions: dict[str, str]
    status: str  # running | no_finding | waiting_approval | completed | failed
    error: str | None
    stats: dict[str, Any]
    versions: dict[str, Any]
