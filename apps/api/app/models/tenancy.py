from sqlalchemy import Boolean, SmallInteger, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, TIMESTAMP

from app.db.base import Base, IdMixin, TimestampMixin
from app.models._h import (
    UUID,
    Mapped,
    datetime,
    enum_ck,
    jsonb,
    mapped_column,
    tenant_fk,
    text_array,
    uuid_fk,
)

ROLES = ("owner", "admin", "manager", "member", "viewer")
DEFAULT_NOTIFICATION_PREFS = (
    '{"digest_channel":"slack","digest_hour":9,"digest_days":"weekdays",'
    '"alert_high":true,"alert_assigned":true,"alert_failed":true}'
)


class Organization(Base, IdMixin, TimestampMixin):
    __tablename__ = "organizations"
    __table_args__ = (enum_ck("status", ("active", "suspended", "deleted")),)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str | None] = mapped_column(Text, unique=True)
    primary_domain: Mapped[str | None] = mapped_column(Text)
    extra_domains: Mapped[list[str]] = text_array()
    timezone: Mapped[str] = mapped_column(Text, server_default="Asia/Kolkata", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), server_default="USD", nullable=False)
    plan: Mapped[str] = mapped_column(Text, server_default="pilot", nullable=False)
    settings: Mapped[dict[str, object]] = jsonb()
    status: Mapped[str] = mapped_column(Text, server_default="active", nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class User(Base, IdMixin, TimestampMixin):
    """Global (not tenant-scoped, no RLS)."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    last_login_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    is_superadmin: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )


class Membership(Base, IdMixin, TimestampMixin):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_memberships_org_id_user_id"),
        enum_ck("role", ROLES),
        enum_ck("status", ("active", "disabled")),
    )

    org_id: Mapped[UUID] = tenant_fk()
    user_id: Mapped[UUID] = uuid_fk("users.id")
    role: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="active", nullable=False)
    crm_owner_id: Mapped[str | None] = mapped_column(Text)
    slack_user_id: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str | None] = mapped_column(Text)
    digest_hour: Mapped[int | None] = mapped_column(SmallInteger)
    notification_prefs: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        server_default=text("'" + DEFAULT_NOTIFICATION_PREFS.replace(":", "\:") + "'::jsonb"),
        nullable=False,
    )


class Invite(Base, IdMixin, TimestampMixin):
    __tablename__ = "invites"
    __table_args__ = (enum_ck("role", ROLES),)

    org_id: Mapped[UUID] = tenant_fk()
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    invited_by: Mapped[UUID | None] = uuid_fk("users.id", nullable=True, ondelete="SET NULL")
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class ApiKey(Base, IdMixin, TimestampMixin):
    __tablename__ = "api_keys"

    org_id: Mapped[UUID] = tenant_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    prefix: Mapped[str] = mapped_column(Text, nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    scopes: Mapped[list[str]] = text_array()
    last_used_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_by: Mapped[UUID | None] = uuid_fk("users.id", nullable=True, ondelete="SET NULL")
