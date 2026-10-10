from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.config import get_settings
from app.ports import ActionPlanner, Explainer, SignalExtractor
from app.ports import registry as reg
from app.ports.template import (
    ExternalPending,
    NullSignalExtractor,
    TemplateActionPlanner,
    TemplateExplainer,
)
from app.ports.types import EventView, ExtractCtx


@pytest.fixture(autouse=True)
def _clean() -> None:
    reg.clear_overrides()
    get_settings.cache_clear()


def test_template_mode_is_default_and_ports_conform() -> None:
    assert get_settings().ai_mode == "template"
    assert isinstance(reg.get_signal_extractor(), NullSignalExtractor)
    assert isinstance(reg.get_explainer(), TemplateExplainer)
    assert isinstance(reg.get_action_planner(), TemplateActionPlanner)
    assert isinstance(reg.get_signal_extractor(), SignalExtractor)
    assert isinstance(reg.get_explainer(), Explainer)
    assert isinstance(reg.get_action_planner(), ActionPlanner)


async def test_null_extractor_returns_no_signals() -> None:
    ev = EventView(
        id=uuid4(),
        account_id=None,
        type="email_in",
        occurred_at=datetime.now(UTC),
        text="we are looking at a competitor",
    )
    assert await reg.get_signal_extractor().extract(ExtractCtx(org_id=uuid4()), ev) == []


def test_external_mode_switches_implementations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_MODE", "external")
    get_settings.cache_clear()
    assert isinstance(reg.get_explainer(), ExternalPending)
    assert isinstance(reg.get_action_planner(), ExternalPending)


def test_invalid_ai_mode_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_MODE", "magic")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()


def test_override_hook_for_tests_and_adapters() -> None:
    class Fake:
        async def extract(self, ctx: object, event: object) -> list[object]:
            return []

    fake = Fake()
    reg.override("signal_extractor", fake)
    assert reg.get_signal_extractor() is fake


def test_no_ai_sdk_is_imported_by_the_backend() -> None:
    """Scope guard: this repo phase contains no AI/ML/LLM code (ports + internal endpoints only)."""
    banned = (
        "import openai",
        "import anthropic",
        "import langchain",
        "import langgraph",
        "import torch",
        "import transformers",
        "from openai",
        "from anthropic",
    )
    root = Path(__file__).parents[1] / "app"
    offenders = [
        str(p)
        for p in root.rglob("*.py")
        if any(b in p.read_text(encoding="utf-8") for b in banned)
    ]
    assert not offenders, offenders
