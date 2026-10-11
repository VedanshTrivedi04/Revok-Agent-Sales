"""Resolve port implementations (and test overrides). Services call these getters.

Both AI modes use the deterministic implementations in-process. With AI_MODE=external the AI
service (apps/ai) upgrades their output asynchronously through /internal/v1, so a finding always
has a valid explanation and cards even when the model is slow, wrong or down.
"""

from app.ports import ActionPlanner, Explainer, SignalExtractor
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
    # AI_MODE=external: signals are written by the AI service through /internal/v1
    return NullSignalExtractor()


def get_explainer() -> Explainer:
    if "explainer" in _overrides:
        return _overrides["explainer"]  # type: ignore[return-value]
    # AI_MODE=external: the template explanation is the baseline every finding starts with; the AI
    # service replaces it through /internal/v1 once its own validators and ours accept the result
    return TemplateExplainer()


def get_action_planner() -> ActionPlanner:
    if "action_planner" in _overrides:
        return _overrides["action_planner"]  # type: ignore[return-value]
    # AI_MODE=external: template cards are the baseline; pending ones are redrafted by the AI
    return TemplateActionPlanner()
