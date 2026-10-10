from typing import Any

from fastapi import Request
from pydantic import BaseModel

from app.auth.deps import current_membership, get_claims
from app.contract import endpoint, real
from app.db.session import org_session
from app.permissions import Action
from app.schemas.identity import Ack
from app.schemas.ops import RuleOut, RulePreviewIn, RulePreviewOut, RulePutIn
from app.services.rules import (
    list_rules_service,
    preview_rule_service,
    put_rule_service,
    rerun_rules_service,
)

PAGE = "D8 Rules"


class RulesRerunIn(BaseModel):
    rule_keys: list[str] = []


@endpoint("GET", "/rules", group="rules", page=PAGE, owner="R", phase=4, access=Action.EDIT_RULES)
async def list_rules() -> list[RuleOut]:
    """All rules with org overrides and defaults."""
    raise NotImplementedError


@endpoint(
    "PUT", "/rules/{key}", group="rules", page=PAGE, owner="R", phase=4, access=Action.EDIT_RULES
)
async def put_rule(key: str, body: RulePutIn) -> RuleOut:
    """Enable/disable a rule or change its params (validated against the rule schema)."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/rules/{key}/preview",
    group="rules",
    page=PAGE,
    owner="R",
    phase=4,
    access=Action.EDIT_RULES,
)
async def preview_rule(key: str, body: RulePreviewIn) -> RulePreviewOut:
    """How many accounts would fire with these params now."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/rules/rerun",
    group="rules",
    page=PAGE,
    owner="R",
    phase=4,
    access=Action.EDIT_RULES,
)
async def rerun_rules(body: RulesRerunIn | None = None) -> Ack:
    """Trigger/enqueue rule detection across active accounts."""
    raise NotImplementedError


# ==============================================================================
# Real Handlers
# ==============================================================================


@real("list_rules")
async def list_rules_real(request: Request, **_: Any) -> list[RuleOut]:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await list_rules_service(s, org_id=m.org_id)


@real("put_rule")
async def put_rule_real(request: Request, key: str, body: RulePutIn, **_: Any) -> RuleOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await put_rule_service(
            s,
            org_id=m.org_id,
            user_id=m.user_id,
            key=key,
            body=body,
        )


@real("preview_rule")
async def preview_rule_real(
    request: Request, key: str, body: RulePreviewIn, **_: Any
) -> RulePreviewOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await preview_rule_service(
            s,
            org_id=m.org_id,
            key=key,
            body=body,
        )


@real("rerun_rules")
async def rerun_rules_real(request: Request, body: RulesRerunIn | None = None, **_: Any) -> Ack:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        rule_keys = body.rule_keys if body else None
        return await rerun_rules_service(
            s,
            org_id=m.org_id,
            user_id=m.user_id,
            rule_keys=rule_keys,
        )
