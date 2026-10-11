"""Prompt/model versioning, evidence hash and canary selection (A6-07).

Every output carries model + prompt versions + evidence hash so a finding can be replayed. Canary:
orgs are bucketed by a stable hash; a percentage of orgs gets the candidate prompt versions.
"""

import hashlib
from dataclasses import dataclass

from revops_ai.domain import Evidence
from revops_ai.llm import prompts

TASKS = ("extract", "explain", "draft")


def evidence_hash(evidence: list[Evidence]) -> str:
    raw = "\n".join(f"{e.key}|{e.kind}|{e.label}|{e.detail or ''}" for e in evidence)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def bucket(org_id: str, salt: str = "prompt_variant") -> int:
    return int(hashlib.sha256(f"{salt}:{org_id}".encode()).hexdigest()[:8], 16) % 100


@dataclass(frozen=True)
class PromptSet:
    versions: dict[str, str]

    def tag(self, task: str) -> str:
        return f"{task}@{self.versions[task]}"


def select_prompts(
    org_id: str, *, canary_pct: int = 0, candidate: dict[str, str] | None = None
) -> PromptSet:
    """Latest stable versions, except for `canary_pct`% of orgs which get `candidate` versions."""
    stable = {t: prompts.available(t)[-1] for t in TASKS if prompts.available(t)}
    if candidate and bucket(org_id) < canary_pct:
        return PromptSet(
            {**stable, **{k: v for k, v in candidate.items() if v in prompts.available(k)}}
        )
    return PromptSet(stable)
