"""Versioned prompt files: revops_ai/prompts/<task>.<semver>.md with ---SYSTEM--- / ---USER--- parts.

Changing a prompt means a NEW file/version plus an eval run (agent.md rule 12). Old versions stay
loadable for replay.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, StrictUndefined

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"
_ENV = Environment(undefined=StrictUndefined, autoescape=False, trim_blocks=False, keep_trailing_newline=False)  # fmt: skip


def _money(v: float | None) -> str:
    return f"${v:,.0f}" if v else "unknown"


_ENV.filters["money"] = _money
_VER = re.compile(r"^(?P<task>[a-z_]+)\.(?P<ver>\d+\.\d+\.\d+)\.md$")


@dataclass(frozen=True)
class Prompt:
    task: str
    version: str
    system: str
    user: str

    @property
    def tag(self) -> str:
        return f"{self.task}@{self.version}"

    def render(self, **ctx: object) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": _ENV.from_string(self.system).render(**ctx).strip()},
            {"role": "user", "content": _ENV.from_string(self.user).render(**ctx).strip()},
        ]


def available(task: str) -> list[str]:
    out = []
    for p in PROMPT_DIR.glob(f"{task}.*.md"):
        m = _VER.match(p.name)
        if m and m["task"] == task:
            out.append(m["ver"])
    return sorted(out, key=lambda v: tuple(int(x) for x in v.split(".")))


@lru_cache
def load(task: str, version: str | None = None) -> Prompt:
    ver = version or available(task)[-1]
    text = (PROMPT_DIR / f"{task}.{ver}.md").read_text(encoding="utf-8")
    m = re.match(r"\s*---SYSTEM---\n(?P<s>.*?)\n---USER---\n(?P<u>.*)\Z", text, re.S)
    if not m:
        raise ValueError(f"prompt {task}@{ver} must contain ---SYSTEM--- and ---USER--- sections")
    return Prompt(task, ver, m["s"].strip(), m["u"].strip())
