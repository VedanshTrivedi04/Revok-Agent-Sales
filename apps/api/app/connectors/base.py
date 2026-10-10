"""Connector protocols and DTOs. No LLM and no business logic here (agent.md rule 2).

Read side (Rajwardhan): implement `Connector`. Write side (Vedansh, executor): implement
`WritableConnector`. OAuth providers also implement `OAuthConnector`. `ConnCtx` (ctx.py) is what
every method receives: org/integration ids, a rate-limited HTTP client and a token getter that
refreshes transparently.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel

from app.schemas.action_payloads import CrmRef

if TYPE_CHECKING:
    from app.connectors.ctx import ConnCtx


class SyncResult(BaseModel):
    fetched: int = 0
    upserted: int = 0
    events_new: int = 0
    new_cursor: dict[str, Any] = {}
    partial: bool = False


class TokenSet(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    token_type: str = "Bearer"
    raw: dict[str, Any] = {}

    def __repr__(self) -> str:  # never print secrets
        return f"TokenSet(expires_at={self.expires_at!r}, token_type={self.token_type!r})"

    __str__ = __repr__


class ExecResult(BaseModel):
    external_ref: dict[str, Any]  # e.g. {"hubspot_task_id": "..."} / {"gmail_draft_id": "..."}
    pre_image: dict[str, Any] | None = None  # values before a CRM write (for revert)
    already_existed: bool = False  # provider-side idempotency hit


@runtime_checkable
class Connector(Protocol):
    provider: ClassVar[str]

    async def test_connection(self, ctx: "ConnCtx") -> None: ...

    async def sync(
        self, ctx: "ConnCtx", cursor: dict[str, Any], *, backfill_days: int | None
    ) -> SyncResult: ...


@runtime_checkable
class OAuthConnector(Connector, Protocol):
    def authorize_url(self, state: str, redirect_uri: str) -> str: ...

    async def exchange_code(self, code: str, redirect_uri: str) -> TokenSet: ...

    async def refresh(self, refresh_token: str) -> TokenSet: ...


@runtime_checkable
class WritableConnector(Connector, Protocol):
    async def find_existing(self, ctx: "ConnCtx", idem_key: str) -> ExecResult | None: ...

    async def apply(
        self, ctx: "ConnCtx", action_type: str, payload: BaseModel, idem_key: str
    ) -> ExecResult: ...

    async def read_current(
        self, ctx: "ConnCtx", ref: CrmRef, fields: list[str]
    ) -> dict[str, Any]: ...
