from sqlalchemy import Boolean, Index, SmallInteger, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP

from app.db.base import Base, IdMixin, TimestampMixin
from app.models._h import (
    UUID,
    Any,
    Mapped,
    datetime,
    enum_ck,
    jsonb,
    mapped_column,
    tenant_fk,
    uuid_fk,
)

TS = TIMESTAMP(timezone=True)
CARD_TYPES = (
    "email_draft", "crm_task", "crm_field_update", "crm_note", "slack_internal", "meeting_request",
)  # fmt: skip
CARD_STATUSES = (
    "proposed", "pending_approval", "approved", "rejected", "executing", "executed", "failed",
    "reverted", "expired", "blocked",
)  # fmt: skip


class ActionCard(Base, IdMixin, TimestampMixin):
    __tablename__ = "action_cards"
    __table_args__ = (
        enum_ck("type", CARD_TYPES),
        enum_ck("status", CARD_STATUSES),
        enum_ck("tier", (1, 2, 3)),
        enum_ck("decision_channel", ("web", "slack", "auto")),
        enum_ck(
            "rejection_reason",
            ("wrong_action", "wrong_content", "not_now", "already_done", "other"),
        ),
        UniqueConstraint("idempotency_key", name="uq_action_cards_idempotency_key"),
        Index("ix_action_cards_org_id_status", "org_id", "status"),
        Index("ix_action_cards_org_id_assignee_user_id", "org_id", "assignee_user_id"),
        Index("ix_action_cards_finding_id", "finding_id"),
    )

    org_id: Mapped[UUID] = tenant_fk()
    account_id: Mapped[UUID] = uuid_fk("accounts.id")
    finding_id: Mapped[UUID | None] = uuid_fk("findings.id", nullable=True, ondelete="SET NULL")
    agent_run_id: Mapped[UUID | None] = uuid_fk("agent_runs.id", nullable=True, ondelete="SET NULL")
    type: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="proposed", nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    evidence_keys: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'"), nullable=False
    )
    payload: Mapped[dict[str, Any]] = jsonb()
    edited_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    preview: Mapped[list[Any]] = jsonb("[]")
    assignee_user_id: Mapped[UUID | None] = uuid_fk("users.id", nullable=True, ondelete="SET NULL")
    decided_by: Mapped[UUID | None] = uuid_fk("users.id", nullable=True, ondelete="SET NULL")
    decided_at: Mapped[datetime | None] = mapped_column(TS)
    decision_channel: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    rejection_note: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    external_ref: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    executed_at: Mapped[datetime | None] = mapped_column(TS)
    reverted_at: Mapped[datetime | None] = mapped_column(TS)
    reverted_by: Mapped[UUID | None] = uuid_fk("users.id", nullable=True, ondelete="SET NULL")
    expires_at: Mapped[datetime | None] = mapped_column(TS)
    error: Mapped[str | None] = mapped_column(Text)


class Execution(Base, IdMixin):
    __tablename__ = "executions"
    __table_args__ = (
        enum_ck("status", ("started", "succeeded", "failed")),
        Index("ix_executions_action_card_id", "action_card_id"),
    )

    org_id: Mapped[UUID] = tenant_fk()
    action_card_id: Mapped[UUID] = uuid_fk("action_cards.id")
    attempt: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    request: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    pre_image: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(TS, server_default=text("now()"), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(TS)
    error: Mapped[str | None] = mapped_column(Text)


class AutonomyPolicy(Base, IdMixin):
    __tablename__ = "autonomy_policies"
    __table_args__ = (
        UniqueConstraint("org_id", "action_type", name="uq_autonomy_policies_org_id_action_type"),
        enum_ck("action_type", CARD_TYPES),
        enum_ck("tier", (1, 2, 3)),
    )

    org_id: Mapped[UUID] = tenant_fk()
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    conditions: Mapped[dict[str, Any]] = jsonb()
    locked: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    updated_by: Mapped[UUID | None] = uuid_fk("users.id", nullable=True, ondelete="SET NULL")
    updated_at: Mapped[datetime] = mapped_column(TS, server_default=text("now()"), nullable=False)
