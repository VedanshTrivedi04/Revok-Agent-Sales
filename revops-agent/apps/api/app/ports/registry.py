"""Resolve port implementations from AI_MODE (and test overrides). Services call these getters."""

from app.config import get_settings
from app.ports import ActionPlanner, Explainer, SignalExtractor
from app.ports.external import (
    ExternalActionPlanner,
    ExternalExplainer,
    ExternalSignalExtractor,
)
from app.ports.template import (
    NullSignalExtractor,
    TemplateActionPlanner,
    TemplateExplainer,
)

_overrides: dict[str, object] = {}


def override(port: str, impl: object) -> None:
    """Swap an implementation (tests, or the AI engineer's in-process adapter)."""
    _overrides[port] = impl


def clear_overrides() -> None:
    _overrides.clear()


def get_signal_extractor() -> SignalExtractor:
    if "signal_extractor" in _overrides:
        return _overrides["signal_extractor"]  # type: ignore[return-value]
    if get_settings().ai_mode == "external":
        return ExternalSignalExtractor()
    return NullSignalExtractor()


def get_explainer() -> Explainer:
    if "explainer" in _overrides:
        return _overrides["explainer"]  # type: ignore[return-value]
    if get_settings().ai_mode == "external":
        return ExternalExplainer()
    return TemplateExplainer()


def get_action_planner() -> ActionPlanner:
    if "action_planner" in _overrides:
        return _overrides["action_planner"]  # type: ignore[return-value]
    if get_settings().ai_mode == "external":
        return ExternalActionPlanner()
    return TemplateActionPlanner()
