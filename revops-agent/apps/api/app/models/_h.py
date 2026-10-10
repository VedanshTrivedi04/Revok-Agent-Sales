"""Shared column helpers for models."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

__all__ = [
    "ARRAY", "JSONB", "PG_UUID", "Any", "Decimal", "Mapped", "UUID", "date", "datetime",
    "enum_ck", "jsonb", "mapped_column", "money", "tenant_fk", "text_array", "uuid_fk",
]  # fmt: skip


def enum_ck(column: str, values: tuple[str | int, ...] | list[str | int]) -> CheckConstraint:
    """Enums are stored as text + CHECK (easier migrations than native enums)."""
    vals = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in values)
    return CheckConstraint(f"{column} IN ({vals})", name=f"{column}_valid")


def jsonb(default: str = "{}") -> Mapped[Any]:
    return mapped_column(JSONB, server_default=text(f"'{default}'::jsonb"), nullable=False)


def money(nullable: bool = True) -> Mapped[Decimal | None]:
    return mapped_column(Numeric(14, 2), nullable=nullable)


def text_array() -> Mapped[list[str]]:
    return mapped_column(ARRAY(Text), server_default=text("'{}'"), nullable=False)


def tenant_fk() -> Mapped[UUID]:
    return mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


def uuid_fk(target: str, *, nullable: bool = False, ondelete: str = "CASCADE") -> Mapped[UUID]:
    return mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(target, ondelete=ondelete), nullable=nullable
    )
