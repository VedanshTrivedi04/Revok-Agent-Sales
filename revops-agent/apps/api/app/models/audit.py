from sqlalchemy import BigInteger, Boolean, Identity, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.base import Base, IdMixin
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


class DecisionLog(Base):
    """Append-only, hash-chained per org. The app role has INSERT, SELECT only."""

    __tablename__ = "decision_log"
    __table_args__ = (
        enum_ck("actor_type", ("user", "agent", "system")),
        enum_ck(
            "entity_type",
            ("finding", "action_card", "integration", "rule", "policy", "member", "org"),
        ),
        Index("ix_decision_log_org_id_id", "org_id", "id"),
        Index("ix_decision_log_org_id_entity", "org_id", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    org_id: Mapped[UUID] = tenant_fk()
    ts: Mapped[datetime] = mapped_column(TS, server_default=text("now()"), nullable=False)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str | None] = mapped_column(Text)
    event: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    account_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    data: Mapped[dict[str, Any]] = jsonb()
    prev_hash: Mapped[str] = mapped_column(Text, nullable=False)
    hash: Mapped[str] = mapped_column(Text, nullable=False)


class Notification(Base, IdMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        enum_ck(
            "kind",
            ("finding_high", "card_assigned", "execution_failed", "integration_error", "digest"),
        ),
        Index("ix_notifications_org_id_user_id_read_at", "org_id", "user_id", "read_at"),
    )

    org_id: Mapped[UUID] = tenant_fk()
    user_id: Mapped[UUID] = uuid_fk("users.id")
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(TS)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=text("now()"), nullable=False)


class FailedJob(Base, IdMixin):
    """Dead-letter for Celery tasks. Global ops table (no RLS); admin routes read it."""

    __tablename__ = "failed_jobs"

    task_name: Mapped[str] = mapped_column(Text, nullable=False)
    args: Mapped[Any] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    traceback: Mapped[str | None] = mapped_column(Text)
    failed_at: Mapped[datetime] = mapped_column(TS, server_default=text("now()"), nullable=False)
    retried_at: Mapped[datetime | None] = mapped_column(TS)


class FeatureFlag(Base):
    """Global flags with optional per-org overrides: {"<org_id>": true}."""

    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    default: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    per_org: Mapped[dict[str, Any]] = jsonb()


class Outcome(Base, IdMixin):
    """Phase 2 (created now, unused)."""

    __tablename__ = "outcomes"
    __table_args__ = (
        enum_ck(
            "kind",
            (
                "reply_received", "meeting_booked", "usage_recovered", "renewal_won",
                "renewal_lost", "no_change",
            ),
        ),
    )  # fmt: skip

    org_id: Mapped[UUID] = tenant_fk()
    action_card_id: Mapped[UUID | None] = uuid_fk(
        "action_cards.id", nullable=True, ondelete="SET NULL"
    )
    finding_id: Mapped[UUID | None] = uuid_fk("findings.id", nullable=True, ondelete="SET NULL")
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    data: Mapped[dict[str, Any]] = jsonb()
    window_days: Mapped[int | None] = mapped_column(Integer)


class EditFeedback(Base, IdMixin):
    """Phase 2 (created now, unused)."""

    __tablename__ = "edit_feedback"

    org_id: Mapped[UUID] = tenant_fk()
    action_card_id: Mapped[UUID] = uuid_fk("action_cards.id")
    user_id: Mapped[UUID | None] = uuid_fk("users.id", nullable=True, ondelete="SET NULL")
    field: Mapped[str] = mapped_column(Text, nullable=False)
    before: Mapped[str | None] = mapped_column(Text)
    after: Mapped[str | None] = mapped_column(Text)
    diff_stats: Mapped[dict[str, Any]] = jsonb()
