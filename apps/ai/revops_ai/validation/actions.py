"""Post-validation of T3 proposals (`validate_actions`, aiengineerhandover.md section 7.3).

Nothing here trusts the model: recipients are resolved from the contact allowlist by id, field updates
must map to a writable property and an allowed value, pricing language is dropped, internal metrics in
customer emails are flagged, evidence ids must exist, duplicates and over-limit items are removed.
The backend re-validates everything again (tier policy, allowlists) - this is the first line only.
"""

import re
from dataclasses import dataclass, field

from revops_ai.domain import Contact, Evidence
from revops_ai.llm.schemas import (
    DraftOutput,
    EmailProposal,
    FieldUpdateProposal,
    Proposal,
    SlackProposal,
    TaskProposal,
)
from revops_ai.validation.numbers import extract_facts, number_supported

BANNED = re.compile(
    r"discount|%\s*off|free\s+months?|price\s+(cut|reduction)|waive|refund|contract\s+(change|amendment)",
    re.I,
)
PLACEHOLDER = re.compile(r"\{\{|\}\}|\[(name|company|insert)[^\]]*\]|<[^>]+>", re.I)
MAX_ACTIONS = 4
RISK_LEVELS = {"high", "medium", "low"}


@dataclass
class Checked:
    proposal: Proposal
    flags: list[str] = field(default_factory=list)


@dataclass
class ActionValidation:
    kept: list[Checked] = field(default_factory=list)
    dropped: list[dict[str, str]] = field(default_factory=list)


def _words(s: str) -> int:
    return len(s.split())


def _metric_numbers(evidence: list[Evidence]) -> list[tuple[float, int]]:
    out: list[tuple[float, int]] = []
    for e in evidence:
        if e.kind == "rule_metric":
            out += [(v, d) for v, d in extract_facts(e.label).numbers if v >= 5]
    return out


def validate_actions(
    out: DraftOutput,
    *,
    contacts: list[Contact],
    evidence: list[Evidence],
    allowed_types: set[str],
    health_values: dict[str, str],
    mapped_fields: set[str] | None = None,
    existing_titles: list[str] | None = None,
) -> ActionValidation:
    res = ActionValidation()
    by_id = {c.id: c for c in contacts}
    keys = {e.key for e in evidence}
    metric_nums = _metric_numbers(evidence)
    mapped = (
        mapped_fields if mapped_fields is not None else {"health", "next_step", "revops_risk_level"}
    )
    seen: list[str] = list(existing_titles or [])

    def drop(p: Proposal, reason: str) -> None:
        res.dropped.append({"type": p.type, "reason": reason})

    for p in out.actions:
        if p.type not in allowed_types:
            drop(p, "type_not_allowed")
            continue
        bad_ev = [k for k in p.evidence_ids if k not in keys]
        if bad_ev:
            drop(p, f"unknown_evidence_id:{','.join(bad_ev)}")
            continue
        flags: list[str] = []
        title = ""
        text_fields: list[str] = []
        if isinstance(p, EmailProposal):
            title = p.subject
            ids = [*p.to_contact_ids, *p.cc_contact_ids]
            unknown = [i for i in ids if i not in by_id]
            inactive = [i for i in ids if i in by_id and not by_id[i].is_active]
            if unknown:
                drop(p, f"recipient_not_in_contacts:{unknown[0]}")
                continue
            if inactive:
                drop(p, "recipient_inactive")
                continue
            text_fields = [p.subject, p.body_text]
            if PLACEHOLDER.search(p.body_text) or PLACEHOLDER.search(p.subject):
                drop(p, "placeholder_left_in_text")
                continue
            n = _words(p.body_text)
            if n < 25 or n > 220:
                drop(p, f"email_length:{n}_words")
                continue
            body_nums = extract_facts(p.body_text).numbers
            if any(number_supported(v, d, metric_nums) for v, d in body_nums if v >= 5):
                flags.append("contains_internal_metric")
        elif isinstance(p, TaskProposal):
            title = p.title
            text_fields = [p.title, p.body]
        elif isinstance(p, FieldUpdateProposal):
            title = f"{p.field_key}={p.new_value}"
            if p.field_key not in mapped:
                drop(p, "field_not_mapped")
                continue
            if p.field_key == "health" and p.new_value not in health_values.values():
                drop(p, "health_value_not_allowed")
                continue
            if p.field_key == "revops_risk_level" and p.new_value.lower() not in RISK_LEVELS:
                drop(p, "risk_level_value_not_allowed")
                continue
            text_fields = [p.new_value]
        elif isinstance(p, SlackProposal):
            title = p.text[:60]
            text_fields = [p.text]
        if any(BANNED.search(t) for t in text_fields + [p.rationale]):
            drop(p, "policy_drop:banned_pricing_language")
            continue
        norm = f"{p.type}:{re.sub(r'\W+', ' ', title.lower()).strip()}"
        if any(norm == s or (p.type == s.split(":")[0] and _similar(norm, s)) for s in seen):
            drop(p, "duplicate")
            continue
        seen.append(norm)
        if len(res.kept) >= MAX_ACTIONS:
            drop(p, "over_limit")
            continue
        res.kept.append(Checked(p, flags))
    return res


def _similar(a: str, b: str) -> bool:
    ta, tb = set(a.split()), set(b.split())
    return bool(ta and tb) and len(ta & tb) / len(ta | tb) >= 0.8
