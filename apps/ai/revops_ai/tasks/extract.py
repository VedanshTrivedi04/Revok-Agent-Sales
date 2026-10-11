"""T1 extract_signals: untrusted email/note text -> validated signals with exact quotes.

Never raises into the graph: on repeated model failure it returns no signals and `failed=True`.
"""

import html
import re
from dataclasses import dataclass, field
from datetime import datetime

import structlog

from revops_ai.llm import prompts
from revops_ai.llm.client import CallMeta, LLMClient, LLMOutputError
from revops_ai.llm.schemas import ExtractOutput, Signal
from revops_ai.validation.injection import redact, scan
from revops_ai.validation.quotes import resolve_overlaps, validate_signals

log = structlog.get_logger()
MAX_CHARS = 3000
KNOWN_COMPETITORS = ["Gainsight", "ChurnZero", "Totango", "Vitally", "Planhat", "ClientSuccess", "Catalyst", "Staircase AI"]  # per-org setting in production  # fmt: skip
OUTBOUND_KINDS = {"new_stakeholder", "renewal_intent"}


@dataclass
class ExtractResult:
    signals: list[Signal] = field(default_factory=list)
    quarantined: bool = False
    failed: bool = False
    skipped: bool = False
    dropped: list[dict[str, str]] = field(default_factory=list)
    prompt_version: str = ""
    model: str = ""
    metas: list[CallMeta] = field(default_factory=list)


def html_to_text(raw: str) -> str:
    if "<" not in raw:
        return raw
    t = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", t)
    t = re.sub(r"(?s)<!--.*?-->", lambda m: m.group(0), t)  # keep comments: injections hide there
    t = re.sub(r"<(?!!--)[^>]+>", " ", t)
    return html.unescape(t)


async def extract_signals(
    llm: LLMClient,
    *,
    text: str,
    org_name: str,
    account_name: str,
    date: datetime,
    inbound: bool = True,
    from_role: str = "unknown",
    prompt_version: str | None = None,
    skip_outbound: bool = True,
    competitors: list[str] | None = None,
) -> ExtractResult:
    p = prompts.load("extract", prompt_version)
    res = ExtractResult(prompt_version=p.tag)
    if not text or not text.strip():
        res.skipped = True
        return res
    if not inbound and skip_outbound:
        res.skipped = True
        return res

    work, hits = scan(text)
    res.quarantined = bool(hits)
    # the model never sees instruction-like sentences (redact by position, then strip HTML)
    safe = html_to_text(redact(work, hits))[:MAX_CHARS]

    messages = p.render(
        org_name=org_name, account_name=account_name, inbound=inbound,
        date=date.date().isoformat(), from_role=from_role, text=safe, competitors=competitors or KNOWN_COMPETITORS,
    )  # fmt: skip
    out: ExtractOutput | None = None
    for attempt in range(2):  # one retry on invalid output
        try:
            out, meta = await llm.call_json("extract", messages, ExtractOutput, temperature=0.0, max_tokens=600)  # fmt: skip
            res.metas.append(meta)
            res.model = meta.model
            break
        except LLMOutputError:
            log.warning("extract_invalid_output", attempt=attempt)
        except Exception as e:  # noqa: BLE001 - transport/TLS/unknown errors must never crash the run
            log.warning("extract_call_failed", attempt=attempt, error_type=type(e).__name__)
    if out is None:
        res.failed = True
    else:
        sigs = [s for s in out.signals if s.kind != "suspicious_instruction"]
        if not inbound:
            sigs = [s for s in sigs if s.kind in OUTBOUND_KINDS]
        res.signals, res.dropped = validate_signals(sigs, [safe])
        res.signals, more = resolve_overlaps(res.signals)
        res.dropped += more

    # deterministic injection signals (do not depend on the model noticing)
    for h in hits:
        if h.quote in text:  # backend validates quote as a substring of the stored event text
            res.signals.append(Signal(kind="suspicious_instruction", polarity="neutral", value=None, quote=h.quote, confidence=0.9))  # fmt: skip
    res.signals = res.signals[:6]
    return res
