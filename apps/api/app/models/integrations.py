from sqlalchemy import ForeignKey, Index, Integer, LargeBinary, Text, func, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

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
    text_array,
    uuid_fk,
)

PROVIDERS = ("hubspot", "gmail", "gcal", "slack", "usage_api", "usage_csv")
NIL_UUID = "00000000-0000-0000-0000-000000000000"


class Integration(Base, IdMixin, TimestampMixin):
    __tablename__ = "integrations"
    __table_args__ = (
        enum_ck("provider", PROVIDERS),
        enum_ck("scope_level", ("org", "user")),
        enum_ck("status", ("connected", "syncing", "needs_reauth", "error", "disconnected")),
        Index(
            "uq_integrations_org_provider_user",
            "org_id",
            "provider",
            text(f"coalesce(user_id, '{NIL_UUID}'::uuid)"),
            unique=True,
        ),
    )

    org_id: Mapped[UUID] = tenant_fk()
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    scope_level: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[UUID | None] = uuid_fk("users.id", nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    external_account_id: Mapped[str | None] = mapped_column(Text)
    external_account_label: Mapped[str | None] = mapped_column(Text)
    scopes: Mapped[list[str]] = text_array()
    cursor: Mapped[dict[str, Any]] = jsonb()
    last_sync_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    error_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)


class OAuthToken(Base, IdMixin, TimestampMixin):
    __tablename__ = "oauth_tokens"

    org_id: Mapped[UUID] = tenant_fk()
    integration_id: Mapped[UUID] = uuid_fk("integrations.id")
    access_token_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    refresh_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    key_id: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    token_type: Mapped[str | None] = mapped_column(Text)


class SyncRun(Base, IdMixin, TimestampMixin):
    __tablename__ = "sync_runs"
    __table_args__ = (
        enum_ck("status", ("running", "success", "partial", "failed")),
        Index("ix_sync_runs_integration_id_started_at", "integration_id", "started_at"),
    )

    org_id: Mapped[UUID] = tenant_fk()
    integration_id: Mapped[UUID] = uuid_fk("integrations.id")
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    status: Mapped[str] = mapped_column(Text, server_default="running", nullable=False)
    stats: Mapped[dict[str, Any]] = jsonb()
    error: Mapped[str | None] = mapped_column(Text)


class FieldMapping(Base):
    """One row per org (PK is org_id)."""

    __tablename__ = "field_mappings"

    org_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    renewal_date_property: Mapped[str | None] = mapped_column(Text)
    arr_property: Mapped[str | None] = mapped_column(Text)
    mrr_property: Mapped[str | None] = mapped_column(Text)
    seats_property: Mapped[str | None] = mapped_column(Text)
    plan_property: Mapped[str | None] = mapped_column(Text)
    health_property: Mapped[str | None] = mapped_column(Text)
    health_values: Mapped[dict[str, Any]] = jsonb()
    next_step_property: Mapped[str] = mapped_column(
        Text, server_default="hs_next_step", nullable=False
    )
    lifecycle_property: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[UUID | None] = uuid_fk("users.id", nullable=True, ondelete="SET NULL")
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
