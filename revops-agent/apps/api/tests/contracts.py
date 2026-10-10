"""Reusable contract suite: run `await check_connector_contract(connector, ctx)` against any
Connector implementation (HubSpot, Gmail, ...). Read-side connectors must pass it; writable
ones additionally prove provider-side idempotency (double apply -> one external object)."""

from typing import Any

from pydantic import BaseModel

from app.connectors.base import Connector, SyncResult, WritableConnector
from app.connectors.ctx import ConnCtx
from app.schemas.action_payloads import CrmNotePayload, CrmRef


async def check_connector_contract(connector: Connector, ctx: ConnCtx) -> None:
    assert isinstance(connector, Connector) and connector.provider
    await connector.test_connection(ctx)

    first = await connector.sync(ctx, {}, backfill_days=30)
    assert isinstance(first, SyncResult)
    assert first.fetched >= first.upserted >= 0 and isinstance(first.new_cursor, dict)
    again = await connector.sync(ctx, first.new_cursor, backfill_days=None)  # resumes from cursor
    assert isinstance(again.new_cursor, dict)

    if isinstance(connector, WritableConnector):
        payload: BaseModel = CrmNotePayload(
            body="hello", associate=[CrmRef(object="company", id="1")]
        )
        key = "idem-contract-1"
        assert await connector.find_existing(ctx, key) is None
        a = await connector.apply(ctx, "crm_note", payload, key)
        b = await connector.apply(
            ctx, "crm_note", payload, key
        )  # double run -> ONE external object
        assert a.external_ref == b.external_ref and b.already_existed and not a.already_existed
        found = await connector.find_existing(ctx, key)
        assert found is not None and found.external_ref == a.external_ref
        current: dict[str, Any] = await connector.read_current(
            ctx, CrmRef(object="company", id="1"), ["health_status"]
        )
        assert "health_status" in current
