"""Opaque keyset (cursor) pagination.

cursor = base64url(JSON of the last row's sort-key values). Order columns must be NOT NULL and
end with a unique column (usually id). Response shape: {items, next_cursor}.
"""

import base64
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql import Select

from app.utils.errors import AppError

DEFAULT_LIMIT = 25
MAX_LIMIT = 100


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None


class PageParams(BaseModel):
    limit: int = DEFAULT_LIMIT
    cursor: str | None = None


def page_params(
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    cursor: Annotated[str | None, Query()] = None,
) -> PageParams:
    return PageParams(limit=limit, cursor=cursor)


@dataclass(frozen=True)
class OrderKey:
    column: InstrumentedAttribute[Any]
    desc: bool = False


def _enc(v: Any) -> Any:
    if isinstance(v, datetime):  # check before date
        return {"dt": v.isoformat()}
    if isinstance(v, date):
        return {"da": v.isoformat()}
    if isinstance(v, UUID):
        return {"u": str(v)}
    if isinstance(v, Decimal):
        return {"d": str(v)}
    return v


def _dec(v: Any) -> Any:
    if isinstance(v, dict):
        ((tag, raw),) = v.items()
        decoders: dict[str, Callable[[Any], Any]] = {
            "dt": datetime.fromisoformat,
            "da": date.fromisoformat,
            "u": UUID,
            "d": Decimal,
        }
        return decoders[tag](raw)
    return v


def encode_cursor(values: list[Any]) -> str:
    raw = json.dumps([_enc(v) for v in values], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str, expected_len: int) -> list[Any]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        values = [_dec(v) for v in json.loads(raw)]
        if not isinstance(values, list) or len(values) != expected_len:
            raise ValueError("shape")
        return values
    except (ValueError, KeyError, TypeError) as e:
        raise AppError("invalid_cursor") from e


async def paginate(
    session: AsyncSession,
    stmt: Select[Any],
    order: list[OrderKey],
    params: PageParams,
) -> tuple[list[Any], str | None]:
    """Run `stmt` (select(Model).where(...)) ordered by `order`; return (rows, next_cursor)."""
    if params.cursor:
        last = decode_cursor(params.cursor, len(order))
        clauses = []
        for i, key in enumerate(order):
            eq = [order[j].column == last[j] for j in range(i)]
            cmp = key.column < last[i] if key.desc else key.column > last[i]
            clauses.append(and_(*eq, cmp))
        stmt = stmt.where(or_(*clauses))
    stmt = stmt.order_by(*[k.column.desc() if k.desc else k.column.asc() for k in order])
    rows = list((await session.execute(stmt.limit(params.limit + 1))).scalars().all())
    next_cursor = None
    if len(rows) > params.limit:
        rows = rows[: params.limit]
        next_cursor = encode_cursor([getattr(rows[-1], k.column.key) for k in order])
    return rows, next_cursor


__all__ = [
    "OrderKey",
    "Page",
    "PageParams",
    "decode_cursor",
    "encode_cursor",
    "page_params",
    "paginate",
    "select",
]
