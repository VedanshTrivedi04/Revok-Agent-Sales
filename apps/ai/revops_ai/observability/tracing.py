"""Tracing, masking and alert rules (A6-06). No customer content leaves the process unmasked.

`RunTrace` records spans (node, duration, small metadata). Sinks: in-memory (tests), JSONL file (local
dashboards) and an optional Langfuse sink built only when LANGFUSE_* keys are configured. Trace payloads
contain evidence labels/hashes and counts, never email bodies.
"""

import hashlib
import json
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from revops_ai.config import Settings

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{8,}\d")


def mask(value: Any) -> Any:
    """Redact emails and phone numbers recursively (Langfuse `mask` function)."""
    if isinstance(value, str):
        return _PHONE.sub("[phone]", _EMAIL.sub("[email]", value))
    if isinstance(value, dict):
        return {k: mask(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [mask(v) for v in value]
    return value


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass
class Span:
    name: str
    started: float
    duration_ms: int = 0
    status: str = "ok"
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunTrace:
    run_id: str
    org_id: str
    account_id: str
    spans: list[Span] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @contextmanager
    def span(self, name: str, **meta: Any) -> Iterator[Span]:
        s = Span(name, time.perf_counter(), meta=dict(meta))
        self.spans.append(s)
        try:
            yield s
        except Exception:
            s.status = "error"
            raise
        finally:
            s.duration_ms = int((time.perf_counter() - s.started) * 1000)

    def to_dict(self) -> dict[str, Any]:
        return mask({
            "run_id": self.run_id, "org_id": self.org_id, "account_id": self.account_id, "meta": self.meta,
            "spans": [{"name": s.name, "duration_ms": s.duration_ms, "status": s.status, "meta": s.meta} for s in self.spans],
        })  # type: ignore[no-any-return]  # fmt: skip


class Sink(Protocol):
    def emit(self, trace: RunTrace) -> None: ...


class MemorySink:
    def __init__(self) -> None:
        self.traces: list[dict[str, Any]] = []

    def emit(self, trace: RunTrace) -> None:
        self.traces.append(trace.to_dict())


class JsonlSink:
    def __init__(self, path: Path) -> None:
        self.path = path

    def emit(self, trace: RunTrace) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(trace.to_dict(), ensure_ascii=False) + "\n")


class LangfuseSink:  # pragma: no cover - needs a Langfuse server
    def __init__(self, settings: Settings) -> None:
        from langfuse import Langfuse

        self.client = Langfuse(host=settings.langfuse_host, public_key=settings.langfuse_public_key, secret_key=settings.langfuse_secret_key, mask=lambda *, data, **_: mask(data))  # fmt: skip

    def emit(self, trace: RunTrace) -> None:
        d = trace.to_dict()
        with self.client.start_as_current_observation(
            name=f"run:{d['run_id']}", as_type="span", metadata=d["meta"]
        ):
            for s in d["spans"]:
                with self.client.start_as_current_observation(name=s["name"], as_type="span", metadata={"duration_ms": s["duration_ms"], **s["meta"]}):  # fmt: skip
                    pass
        self.client.flush()


def sink_from_settings(s: Settings) -> Sink | None:
    return LangfuseSink(s) if s.langfuse_host and s.langfuse_public_key else None


# ---------------- alert rules (aiengineerhandover.md section 9)
def check_alerts(runs: list[dict[str, Any]]) -> list[str]:
    """runs: [{fallback: bool, llm_latency_ms: [..]}] within the last hour."""
    alerts: list[str] = []
    if runs and sum(1 for r in runs if r.get("fallback")) / len(runs) > 0.20:
        alerts.append("fallback_rate_over_20pct")
    lat = sorted(x for r in runs for x in r.get("llm_latency_ms", []))
    if lat and lat[min(len(lat) - 1, int(0.95 * len(lat)))] > 20_000:
        alerts.append("llm_p95_over_20s")
    return alerts
