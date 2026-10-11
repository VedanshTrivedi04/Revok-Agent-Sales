"""The two seams of the AI service: where context comes from, and where results go.

In production both are implemented over `/internal/v1` (adapters/internal_client.py). For development
and tests they are implemented in-process (fixtures + FakeBackend). The graph only sees these protocols.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

from revops_ai.adapters.backend_contract import BackendProposal
from revops_ai.domain import Fixture
from revops_ai.llm.schemas import Signal
from revops_ai.tasks.explain import Explanation


@dataclass
class ProposalsSaved:
    created_card_ids: list[str] = field(default_factory=list)
    tiers: dict[str, int] = field(default_factory=dict)  # card_id -> tier
    rejected: list[dict[str, Any]] = field(default_factory=list)


class ContextProvider(Protocol):
    async def load(self, org_id: str, account_id: str) -> Fixture: ...

    async def finding_id(self, org_id: str, account_id: str) -> str: ...


class BackendPort(Protocol):
    async def save_signals(self, org_id: str, event_id: str, signals: list[Signal], model: str, prompt_version: str) -> int: ...  # fmt: skip

    async def save_explanation(self, org_id: str, finding_id: str, ex: Explanation) -> tuple[bool, list[str]]: ...  # fmt: skip

    async def save_proposals(self, org_id: str, finding_id: str, proposals: list[BackendProposal]) -> ProposalsSaved: ...  # fmt: skip

    async def run_status(self, org_id: str, run_id: str, status: str, stats: dict[str, Any], error: str | None = None) -> None: ...  # fmt: skip
