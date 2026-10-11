from sqlalchemy import (
    Boolean,
    Date,
    Float,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.base import Base, IdMixin, TimestampMixin
from app.models._h import (
    UUID,
    Any,
    Decimal,
    Mapped,
    date,
    datetime,
    enum_ck,
    jsonb,
    mapped_column,
    tenant_fk,
    text_array,
    uuid_fk,
)

TS = TIMESTAMP(timezone=True)
EVENT_SOURCES = ("hubspot", "gmail", "gcal", "usage", "slack", "system")
EVENT_TYPES = (
    "email_in", "email_out", "meeting", "meeting_cancelled", "note", "task", "call",
    "deal_stage_change", "deal_created", "property_change", "contact_added", "contact_left",
    "usage_snapshot", "ticket", "payment_failed",
)  # fmt: skip
MATCH_METHODS = ("crm_association", "contact_email", "domain", "manual", "none")


class Account(Base, IdMixin, TimestampMixin):
    __tablename__ = "accounts"
    __table_args__ = (
        enum_ck("status", ("active", "churned", "prospect", "archived")),
        Index("ix_accounts_org_id_owner_user_id", "org_id", "owner_user_id"),
        Index(
            "ix_accounts_org_id_priority_score", "org_id", text("priority_score DESC NULLS LAST")
        ),
        Index("ix_accounts_domains", "domains", postgresql_using="gin"),
        Index("ix_accounts_name_trgm", text("lower(name) gin_trgm_ops"), postgresql_using="gin"),
    )

    org_id: Mapped[UUID] = tenant_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    domains: Mapped[list[str]] = text_array()
    external_ids: Mapped[dict[str, Any]] = jsonb()
    # churn/expansion scores from the AI service's ML model (AI_MODE=external); None = not scored
    ml_scores: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    owner_user_id: Mapped[UUID | None] = uuid_fk("users.id", nullable=True, ondelete="SET NULL")
    crm_owner_id: Mapped[str | None] = mapped_column(Text)
    arr: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    plan_name: Mapped[str | None] = mapped_column(Text)
    seats_purchased: Mapped[int | None] = mapped_column(Integer)
    renewal_date: Mapped[date | None] = mapped_column(Date)
    lifecycle_stage: Mapped[str | None] = mapped_column(Text)
    crm_health: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="active", nullable=False)
    risk_level: Mapped[str | None] = mapped_column(Text)
    priority_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    last_activity_at: Mapped[datetime | None] = mapped_column(TS)
    last_run_at: Mapped[datetime | None] = mapped_column(TS)
    crm_url: Mapped[str | None] = mapped_column(Text)


class Contact(Base, IdMixin, TimestampMixin):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("org_id", "email", name="uq_contacts_org_id_email"),)

    org_id: Mapped[UUID] = tenant_fk()
    account_id: Mapped[UUID | None] = uuid_fk("accounts.id", nullable=True, ondelete="SET NULL")
    external_id: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    role_tags: Mapped[list[str]] = text_array()
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    left_company_at: Mapped[datetime | None] = mapped_column(TS)
    last_inbound_at: Mapped[datetime | None] = mapped_column(TS)
    last_outbound_at: Mapped[datetime | None] = mapped_column(TS)
    crm_url: Mapped[str | None] = mapped_column(Text)


class Deal(Base, IdMixin, TimestampMixin):
    __tablename__ = "deals"
    __table_args__ = (
        enum_ck("deal_type", ("new", "renewal", "expansion", "other")),
        Index("ix_deals_org_id_account_id", "org_id", "account_id"),
    )

    org_id: Mapped[UUID] = tenant_fk()
    account_id: Mapped[UUID] = uuid_fk("accounts.id")
    external_id: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    pipeline: Mapped[str | None] = mapped_column(Text)
    stage: Mapped[str | None] = mapped_column(Text)
    stage_label: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    close_date: Mapped[date | None] = mapped_column(Date)
    deal_type: Mapped[str] = mapped_column(Text, server_default="other", nullable=False)
    next_step: Mapped[str | None] = mapped_column(Text)
    is_closed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    is_won: Mapped[bool | None] = mapped_column(Boolean)
    crm_url: Mapped[str | None] = mapped_column(Text)
    updated_at_source: Mapped[datetime | None] = mapped_column(TS)


class Event(Base, IdMixin, TimestampMixin):
    """The timeline: one row per source record."""

    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "source", "source_record_id", name="uq_events_org_source_record"
        ),
        enum_ck("source", EVENT_SOURCES),
        enum_ck("type", EVENT_TYPES),
        enum_ck("match_method", MATCH_METHODS),
        Index(
            "ix_events_org_id_account_id_occurred_at",
            "org_id",
            "account_id",
            text("occurred_at DESC"),
        ),
    )

    org_id: Mapped[UUID] = tenant_fk()
    account_id: Mapped[UUID | None] = uuid_fk("accounts.id", nullable=True, ondelete="SET NULL")
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_record_id: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(TS, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text)
    participants: Mapped[list[Any]] = jsonb("[]")
    thread_id: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict[str, Any]] = jsonb()
    content_hash: Mapped[str | None] = mapped_column(Text)
    match_method: Mapped[str] = mapped_column(Text, server_default="none", nullable=False)
    match_confidence: Mapped[float] = mapped_column(Float, server_default=text("0"), nullable=False)
    signals_extracted_at: Mapped[datetime | None] = mapped_column(TS)


class UsageSnapshot(Base, IdMixin, TimestampMixin):
    __tablename__ = "usage_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "account_id", "period_start", "granularity", name="uq_usage_snapshots_period"
        ),
        enum_ck("granularity", ("day", "week")),
        enum_ck("source", ("api", "csv")),
    )

    org_id: Mapped[UUID] = tenant_fk()
    account_id: Mapped[UUID] = uuid_fk("accounts.id")
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    granularity: Mapped[str] = mapped_column(Text, nullable=False)
    active_users: Mapped[int] = mapped_column(Integer, nullable=False)
    seats_used: Mapped[int | None] = mapped_column(Integer)
    logins: Mapped[int | None] = mapped_column(Integer)
    key_events: Mapped[dict[str, Any]] = jsonb()
    source: Mapped[str] = mapped_column(Text, nullable=False)


class EntityMatchReview(Base, IdMixin, TimestampMixin):
    __tablename__ = "entity_match_reviews"
    __table_args__ = (enum_ck("status", ("open", "resolved", "ignored")),)

    org_id: Mapped[UUID] = tenant_fk()
    event_id: Mapped[UUID] = uuid_fk("events.id")
    candidate_account_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), server_default=text("'{}'"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="open", nullable=False)
    resolved_account_id: Mapped[UUID | None] = uuid_fk(
        "accounts.id", nullable=True, ondelete="SET NULL"
    )
    resolved_by: Mapped[UUID | None] = uuid_fk("users.id", nullable=True, ondelete="SET NULL")
