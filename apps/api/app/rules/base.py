"""Rules registry, Hit model, and evaluation runner (R3-02)."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.services.context import AccountContext


@dataclass
class Ref:
    kind: str
    ref_ids: list[UUID] = field(default_factory=list)


@dataclass
class RuleHit:
    rule_key: str
    category: str
    finding_type: str  # "risk" or "expansion"
    severity_points: int  # 1 = low, 2 = medium, 3 = high
    metrics: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[Ref] = field(default_factory=list)


@dataclass
class RuleDefinition:
    key: str
    category: str
    finding_type: str
    params_cls: type[BaseModel]
    fn: Callable[[AccountContext, Any], RuleHit | None]
    requires_signals: bool = False


_RULES: dict[str, RuleDefinition] = {}


def rule(
    key: str,
    category: str,
    finding_type: str,
    params_cls: type[BaseModel],
    requires_signals: bool = False,
) -> Callable[
    [Callable[[AccountContext, Any], RuleHit | None]],
    Callable[[AccountContext, Any], RuleHit | None],
]:
    """Register a rule function."""

    def decorator(
        fn: Callable[[AccountContext, Any], RuleHit | None],
    ) -> Callable[[AccountContext, Any], RuleHit | None]:
        _RULES[key] = RuleDefinition(
            key=key,
            category=category,
            finding_type=finding_type,
            params_cls=params_cls,
            fn=fn,
            requires_signals=requires_signals,
        )
        return fn

    return decorator


def get_rule_definitions() -> list[RuleDefinition]:
    return list(_RULES.values())


def evaluate_rules(
    ctx: AccountContext,
    org_overrides: dict[str, dict[str, Any]] | None = None,
) -> list[RuleHit]:
    """Evaluate all registered rules on the account context with optional per-org overrides."""
    overrides = org_overrides or {}
    hits: list[RuleHit] = []

    for key, rdef in _RULES.items():
        # Check if rule is disabled for this org
        rule_override = overrides.get(key)
        if rule_override and not rule_override.get("enabled", True):
            continue

        raw_params = (rule_override or {}).get("params") or {}
        try:
            params_obj = rdef.params_cls.model_validate(raw_params)
        except Exception:
            params_obj = rdef.params_cls()

        hit = rdef.fn(ctx, params_obj)
        if hit is not None:
            hits.append(hit)

    return hits
