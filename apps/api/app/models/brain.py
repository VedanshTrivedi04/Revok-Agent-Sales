from sqlalchemy import Boolean, Float, Index, Numeric, SmallInteger, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.base import Base, IdMixin, TimestampMixin
from app.models._h import (
    UUID,
    Any,
    Decimal,
    Mapped,
    datetime,
    enum_ck,
    jsonb,
    mapped_column,
    tenant_fk,
    text_array,
    uuid_fk,
)

TS = TIMESTAMP(timezone=True)
SIGNAL_KINDS = (
    "sentiment", "competitor_mention", "champion_leaving", "pricing_concern", "budget_cut",
    "escalation", "feature_request", "upgrade_intent", "renewal_intent", "new_stakeholder",
    "suspicious_instruction",
)  # fmt: skip
CATEGORIES = (
    "engagement", "stakeholder", "usage", "sentiment", "renewal", "support", "billing", "expansion",
)  # fmt: skip
FINDING_STATUSES = (
    "open", "in_review", "actioned", "dismissed", "snoozed", "expired", "needs_review", "resolved",
)  # fmt: skip


class AgentRun(Base, IdMixin, TimestampMixin):
    __tablename__ = "agent_runs"
    __table_args__ = (
        enum_ck("trigger", ("nightly", "manual", "webhook", "retry")),
        enum_ck(
            "status", ("queued", "running", "waiting_approval", "completed", "failed", "skipped")
        ),
        Index("ix_agent_runs_org_id_account_id", "org_id", "account_id"),
    )

    org_id: Mapped[UUID] = tenant_fk()
    account_id: Mapped[UUID | None] = uuid_fk("accounts.id", nullable=True, ondelete="SET NULL")
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_by: Mapped[UUID | None] = uuid_fk("users.id", nullable=True, ondelete="SET NULL")
    thread_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="queued", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(TS)
    finished_at: Mapped[datetime | None] = mapped_column(TS)
    stats: Mapped[dict[str, Any]] = jsonb()
    model: Mapped[str | None] = mapped_column(Text)
    prompt_versions: Mapped[dict[str, Any]] = jsonb()
    error: Mapped[str | None] = mapped_column(Text)


class Signal(Base, IdMixin):
    __tablename__ = "signals"
    __table_args__ = (
        enum_ck("kind", SIGNAL_KINDS),
        enum_ck("polarity", ("negative", "positive", "neutral")),
        Index("ix_signals_org_id_account_id", "org_id", "account_id"),
    )

    org_id: Mapped[UUID] = tenant_fk()
    account_id: Mapped[UUID] = uuid_fk("accounts.id")
    event_id: Mapped[UUID] = uuid_fk("events.id")
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    polarity: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[dict[str, Any]] = jsonb()
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    quote: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=text("now()"), nullable=False)


class Rule(Base, IdMixin):
    """Per-org overrides; defaults live in code."""

    __tablename__ = "rules"
    __table_args__ = (UniqueConstraint("org_id", "key", name="uq_rules_org_id_key"),)

    org_id: Mapped[UUID] = tenant_fk()
    key: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    params: Mapped[dict[str, Any]] = jsonb()
    updated_by: Mapped[UUID | None] = uuid_fk("users.id", nullable=True, ondelete="SET NULL")
    updated_at: Mapped[datetime] = mapped_column(TS, server_default=text("now()"), nullable=False)


class RuleHit(Base, IdMixin):
    __tablename__ = "rule_hits"
    __table_args__ = (
        enum_ck("category", CATEGORIES),
        enum_ck("finding_type", ("risk", "expansion")),
        Index("ix_rule_hits_org_id_account_id", "org_id", "account_id"),
    )

    org_id: Mapped[UUID] = tenant_fk()
    account_id: Mapped[UUID] = uuid_fk("accounts.id")
    agent_run_id: Mapped[UUID | None] = uuid_fk("agent_runs.id", nullable=True, ondelete="SET NULL")
    rule_key: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    finding_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity_points: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    metrics: Mapped[dict[str, Any]] = jsonb()
    evidence_refs: Mapped[list[Any]] = jsonb("[]")
    created_at: Mapped[datetime] = mapped_column(TS, server_default=text("now()"), nullable=False)


class Finding(Base, IdMixin, TimestampMixin):
    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("org_id", "fingerprint", name="uq_findings_org_id_fingerprint"),
        enum_ck("type", ("risk", "expansion")),
        enum_ck("status", FINDING_STATUSES),
        enum_ck("severity", ("high", "medium", "low")),
        enum_ck("dismissed_reason", ("not_relevant", "already_handled", "wrong_data", "other")),
        Index("ix_findings_org_id_account_id_status", "org_id", "account_id", "status"),
        Index("ix_findings_org_id_priority_score", "org_id", text("priority_score DESC")),
        Index(
            "ix_findings_org_id_status_priority_score",
            "org_id",
            "status",
            text("priority_score DESC"),
        ),
    )

    org_id: Mapped[UUID] = tenant_fk()
    account_id: Mapped[UUID] = uuid_fk("accounts.id")
    type: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="open", nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    priority_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    claims: Mapped[list[Any]] = jsonb("[]")
    unknowns: Mapped[list[Any]] = jsonb("[]")
    contradictions: Mapped[list[Any]] = jsonb("[]")
    rule_keys: Mapped[list[str]] = text_array()
    categories: Mapped[list[str]] = text_array()
    value_at_stake: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    renewal_in_days: Mapped[int | None] = mapped_column(SmallInteger)
    first_seen_at: Mapped[datetime] = mapped_column(
        TS, server_default=text("now()"), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(TS, server_default=text("now()"), nullable=False)
    dismissed_reason: Mapped[str | None] = mapped_column(Text)
    dismissed_note: Mapped[str | None] = mapped_column(Text)
    snoozed_until: Mapped[datetime | None] = mapped_column(TS)
    agent_run_id: Mapped[UUID | None] = uuid_fk("agent_runs.id", nullable=True, ondelete="SET NULL")
    model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    previous_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class FindingEvidence(Base, IdMixin):
    __tablename__ = "finding_evidence"
    __table_args__ = (
        UniqueConstraint("finding_id", "evidence_key", name="uq_finding_evidence_finding_id_key"),
        enum_ck(
            "kind",
            ("event", "usage", "deal", "contact", "account_field", "signal", "rule_metric"),
        ),
    )

    org_id: Mapped[UUID] = tenant_fk()
    finding_id: Mapped[UUID] = uuid_fk("findings.id")
    evidence_key: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    ref_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    label: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime | None] = mapped_column(TS)
