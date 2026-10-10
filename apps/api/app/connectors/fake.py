"""FakeConnector: deterministic in-memory connector for tests and local development."""

from datetime import timedelta
from typing import Any

from pydantic import BaseModel

from app.connectors.base import ExecResult, SyncResult, TokenSet
from app.connectors.ctx import ConnCtx
from app.schemas.action_payloads import CrmRef
from app.utils.errors import AppError
from app.utils.time import utcnow


class FakeConnector:
    def __init__(
        self,
        *,
        provider: str = "fake",
        pages: list[SyncResult] | None = None,
        fail_refresh: bool = False,
    ) -> None:
        self.provider = provider
        self.pages = list(
            pages or [SyncResult(fetched=3, upserted=3, events_new=2, new_cursor={"ts": 1})]
        )
        self.fail_refresh = fail_refresh
        self.calls: list[str] = []
        self.refresh_count = 0
        self.applied: dict[str, ExecResult] = {}
        self.records: dict[str, dict[str, Any]] = {"company:1": {"health_status": "Green"}}

    # --- Connector
    async def test_connection(self, ctx: ConnCtx) -> None:
        self.calls.append("test_connection")

    async def sync(
        self, ctx: ConnCtx, cursor: dict[str, Any], *, backfill_days: int | None
    ) -> SyncResult:
        self.calls.append("sync")
        page = self.pages.pop(0) if len(self.pages) > 1 else self.pages[0]
        return page.model_copy(update={"new_cursor": {**cursor, **page.new_cursor}})

    # --- OAuthConnector
    def authorize_url(self, state: str, redirect_uri: str) -> str:
        return f"https://fake.example.test/authorize?state={state}&redirect_uri={redirect_uri}"

    async def exchange_code(self, code: str, redirect_uri: str) -> TokenSet:
        return TokenSet(
            access_token=f"access-{code}",
            refresh_token="refresh-1",
            expires_at=utcnow() + timedelta(hours=1),
        )

    async def refresh(self, refresh_token: str) -> TokenSet:
        self.calls.append("refresh")
        self.refresh_count += 1
        if self.fail_refresh:
            raise AppError("integration_needs_reauth", "refresh token revoked")
        return TokenSet(
            access_token=f"access-refreshed-{self.refresh_count}",
            refresh_token=refresh_token,
            expires_at=utcnow() + timedelta(hours=1),
        )

    # --- WritableConnector
    async def find_existing(self, ctx: ConnCtx, idem_key: str) -> ExecResult | None:
        found = self.applied.get(idem_key)
        return found.model_copy(update={"already_existed": True}) if found else None

    async def apply(
        self, ctx: ConnCtx, action_type: str, payload: BaseModel, idem_key: str
    ) -> ExecResult:
        self.calls.append(f"apply:{action_type}")
        if idem_key in self.applied:  # provider-side idempotency
            return self.applied[idem_key].model_copy(update={"already_existed": True})
        pre = dict(self.records.get("company:1", {})) if action_type == "crm_field_update" else None
        res = ExecResult(external_ref={"fake_id": f"obj-{len(self.applied) + 1}"}, pre_image=pre)
        self.applied[idem_key] = res
        return res

    async def read_current(self, ctx: ConnCtx, ref: CrmRef, fields: list[str]) -> dict[str, Any]:
        rec = self.records.get(f"{ref.object}:{ref.id}", {})
        return {f: rec.get(f) for f in fields}
