"""HubSpot write-side handlers.

Implements WritableConnector for:
  - crm_task       : create task with associations
  - crm_note       : create engagement note with associations
  - crm_field_update: update company/deal/contact properties
    Before any update: read_current → compare with card's `before` value →
    mismatch raises FatalError(stale_preview) per algorithm.md §12.

Provider-side idempotency: search for object with property revops_card_id = idem_key.
Pre-image: values before the update, stored in Execution.pre_image for revert.

This module is built for testing with respx mocks; actual HubSpot API calls are
hidden behind ConnCtx.request() which handles auth, rate-limits, retries.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.connectors.base import ExecResult
from app.connectors.ctx import ConnCtx
from app.schemas.action_payloads import (
    CrmFieldUpdatePayload,
    CrmNotePayload,
    CrmRef,
    CrmTaskPayload,
)
from app.utils.errors import FatalError

log = structlog.get_logger()

# HubSpot base API URL
HS_BASE = "https://api.hubapi.com"

# Custom property we stamp on every object created by this system for idempotency
IDEM_PROP = "revops_card_id"


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


async def _hs_get(ctx: ConnCtx, path: str, **kwargs: Any) -> Any:
    return await ctx.request("GET", f"{HS_BASE}{path}", **kwargs)


async def _hs_post(ctx: ConnCtx, path: str, json: Any) -> Any:
    return await ctx.request("POST", f"{HS_BASE}{path}", json=json)


async def _hs_patch(ctx: ConnCtx, path: str, json: Any) -> Any:
    return await ctx.request("PATCH", f"{HS_BASE}{path}", json=json)


async def _hs_delete(ctx: ConnCtx, path: str) -> Any:
    return await ctx.request("DELETE", f"{HS_BASE}{path}")


def _search_by_idem(object_type: str, idem_key: str) -> dict[str, Any]:
    return {
        "filterGroups": [
            {"filters": [{"propertyName": IDEM_PROP, "operator": "EQ", "value": idem_key}]}
        ],
        "properties": ["hs_object_id", IDEM_PROP],
        "limit": 1,
    }


# ---------------------------------------------------------------------------
# crm_task handler
# ---------------------------------------------------------------------------


class HubSpotTaskHandler:
    """Create a HubSpot Task (TASK engagement type)."""

    provider = "hubspot"

    async def find_existing(self, ctx: ConnCtx, idem_key: str) -> ExecResult | None:
        resp = await _hs_post(
            ctx, "/crm/v3/objects/tasks/search", _search_by_idem("tasks", idem_key)
        )
        results = resp.get("results", []) if isinstance(resp, dict) else []
        if results:
            obj_id = str(results[0]["id"])
            return ExecResult(
                external_ref={"hubspot_task_id": obj_id},
                already_existed=True,
            )
        return None

    async def apply(
        self, ctx: ConnCtx, action_type: str, payload: CrmTaskPayload, idem_key: str
    ) -> ExecResult:
        body: dict[str, Any] = {
            "properties": {
                "hs_task_subject": payload.title,
                "hs_task_body": payload.body,
                "hs_timestamp": payload.due_date.isoformat() + "T00:00:00Z",
                "hs_task_status": "NOT_STARTED",
                "hs_task_priority": payload.priority,
                "hubspot_owner_id": payload.owner_crm_id,
                IDEM_PROP: idem_key,
            },
            "associations": [
                {
                    "to": {"id": ref.id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": _assoc_type_id("tasks", ref.object),
                        }
                    ],
                }
                for ref in payload.associate
            ],
        }
        resp = await _hs_post(ctx, "/crm/v3/objects/tasks", body)
        obj_id = str(resp["id"])
        log.info("hubspot_task_created", task_id=obj_id, idem_key=idem_key)
        return ExecResult(external_ref={"hubspot_task_id": obj_id}, pre_image=None)

    async def read_current(self, ctx: ConnCtx, ref: CrmRef, fields: list[str]) -> dict[str, Any]:
        resp = await _hs_get(
            ctx, f"/crm/v3/objects/tasks/{ref.id}", params={"properties": ",".join(fields)}
        )
        return {f: resp.get("properties", {}).get(f) for f in fields}


# ---------------------------------------------------------------------------
# crm_note handler
# ---------------------------------------------------------------------------


class HubSpotNoteHandler:
    """Create a HubSpot Note (NOTE engagement type)."""

    provider = "hubspot"

    async def find_existing(self, ctx: ConnCtx, idem_key: str) -> ExecResult | None:
        resp = await _hs_post(
            ctx, "/crm/v3/objects/notes/search", _search_by_idem("notes", idem_key)
        )
        results = resp.get("results", []) if isinstance(resp, dict) else []
        if results:
            return ExecResult(
                external_ref={"hubspot_note_id": str(results[0]["id"])}, already_existed=True
            )
        return None

    async def apply(
        self, ctx: ConnCtx, action_type: str, payload: CrmNotePayload, idem_key: str
    ) -> ExecResult:
        body: dict[str, Any] = {
            "properties": {
                "hs_note_body": payload.body,
                IDEM_PROP: idem_key,
            },
            "associations": [
                {
                    "to": {"id": ref.id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": _assoc_type_id("notes", ref.object),
                        }
                    ],
                }
                for ref in payload.associate
            ],
        }
        resp = await _hs_post(ctx, "/crm/v3/objects/notes", body)
        obj_id = str(resp["id"])
        log.info("hubspot_note_created", note_id=obj_id, idem_key=idem_key)
        return ExecResult(external_ref={"hubspot_note_id": obj_id}, pre_image=None)

    async def read_current(self, ctx: ConnCtx, ref: CrmRef, fields: list[str]) -> dict[str, Any]:
        resp = await _hs_get(
            ctx, f"/crm/v3/objects/notes/{ref.id}", params={"properties": ",".join(fields)}
        )
        return {f: resp.get("properties", {}).get(f) for f in fields}


# ---------------------------------------------------------------------------
# crm_field_update handler (with stale_preview check per algorithm.md §12)
# ---------------------------------------------------------------------------

_OBJECT_PATHS = {
    "company": "/crm/v3/objects/companies",
    "deal": "/crm/v3/objects/deals",
    "contact": "/crm/v3/objects/contacts",
}


class HubSpotFieldUpdateHandler:
    """Update CRM properties with pre-image capture and stale_preview guard."""

    provider = "hubspot"

    async def find_existing(self, ctx: ConnCtx, idem_key: str) -> ExecResult | None:
        # Field updates are not searchable by idem key; rely on pre_image in Execution table.
        # Return None → always attempt apply (idempotency guaranteed by the card lock).
        return None

    async def apply(
        self,
        ctx: ConnCtx,
        action_type: str,
        payload: CrmFieldUpdatePayload,
        idem_key: str,
    ) -> ExecResult:
        pre_image: dict[str, Any] = {}
        applied: list[dict[str, Any]] = []

        for change in payload.changes:
            path = _OBJECT_PATHS.get(change.object)
            if not path:
                raise FatalError(f"Unknown CRM object type: {change.object}")

            # --- stale_preview check (algorithm.md §12) ---
            current_props = await self.read_current(
                ctx, CrmRef(object=change.object, id=change.id), [change.field]
            )
            current_val = current_props.get(change.field)

            # `before` is the value the card was generated with (snapshotted at propose time)
            if change.before is not None and str(current_val or "") != str(change.before):
                raise FatalError(
                    f"stale_preview:{change.field}:{change.object}:{change.id}:"
                    f"current={current_val!r}:ours={change.before!r}"
                )

            # Store pre-image (value before our write)
            pre_image[f"{change.object}:{change.id}:{change.field}"] = current_val

            # --- apply the update ---
            await _hs_patch(
                ctx, f"{path}/{change.id}", {"properties": {change.field: change.after}}
            )
            applied.append(
                {
                    "object": change.object,
                    "id": change.id,
                    "field": change.field,
                    "after": change.after,
                }
            )

        log.info("hubspot_fields_updated", changes=len(applied), idem_key=idem_key)
        return ExecResult(
            external_ref={"changes": applied, IDEM_PROP: idem_key},
            pre_image=pre_image,
        )

    async def read_current(self, ctx: ConnCtx, ref: CrmRef, fields: list[str]) -> dict[str, Any]:
        path = _OBJECT_PATHS.get(ref.object, f"/crm/v3/objects/{ref.object}s")
        resp = await _hs_get(ctx, f"{path}/{ref.id}", params={"properties": ",".join(fields)})
        return {f: resp.get("properties", {}).get(f) for f in fields}


# ---------------------------------------------------------------------------
# Association type-id helper (HubSpot default association type IDs)
# ---------------------------------------------------------------------------

_ASSOC_TYPE_IDS: dict[tuple[str, str], int] = {
    ("tasks", "company"): 192,
    ("tasks", "deal"): 216,
    ("tasks", "contact"): 204,
    ("notes", "company"): 190,
    ("notes", "deal"): 214,
    ("notes", "contact"): 202,
}


def _assoc_type_id(from_obj: str, to_obj: str) -> int:
    return _ASSOC_TYPE_IDS.get((from_obj, to_obj), 1)


# ---------------------------------------------------------------------------
# Singleton handler instances (registered into executor.core at import time)
# ---------------------------------------------------------------------------

hubspot_task_handler = HubSpotTaskHandler()
hubspot_note_handler = HubSpotNoteHandler()
hubspot_field_update_handler = HubSpotFieldUpdateHandler()
