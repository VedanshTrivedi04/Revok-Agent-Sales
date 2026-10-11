"""HeuristicLLM: a deterministic stand-in for the model used for offline plumbing tests and CI.

It is NOT a quality benchmark (it is derived from the same templates as the synthetic data). Its
purpose is to exercise the whole pipeline - client protocol, prompts, validators, metrics - without
a GPU, and to simulate failure modes (hallucinated quotes, invalid JSON, instruction-following).
Real quality numbers come from the live Qwen3.5-9B endpoint (`--live`).
"""

import re
from typing import Literal, TypeVar

from pydantic import BaseModel

from revops_ai.llm.client import CallMeta, LLMOutputError
from revops_ai.llm.schemas import DraftOutput, ExplainOutput, ExtractOutput, Signal
from revops_ai.synth.messages import BANK

T = TypeVar("T", bound=BaseModel)
Mode = Literal["perfect", "hallucinate", "garbage", "obey_injection"]
ExplainMode = Literal["perfect", "bad_ids", "bad_numbers", "speculative", "pricing", "bad_then_good", "garbage", "one_claim"]  # fmt: skip
DraftMode = Literal["perfect", "bad_recipient", "banned", "leak_metric", "bad_field", "bad_evidence", "placeholder", "duplicates", "garbage", "obey_injection"]  # fmt: skip
_CONTACT = re.compile(
    r"^- (ct-[^ ]+) \| ([^|]*) \| ([^|]*) \| roles: ([^|]*) \| active: (True|False)$", re.M
)
_EVSHORT = re.compile(r"^(E\d{1,2}) \| (.*)$", re.M)
_EVLINE = re.compile(r"^(E\d{1,2}) \| ([^|]*) \| ([^|]*) \| (.*)$", re.M)


def _compile() -> list[tuple[str, str, re.Pattern[str], str | None]]:
    out = []
    for kind, bank in BANK.items():
        if kind == "suspicious_instruction":
            continue
        for pol, tpl, slot in bank:
            rx = re.escape(tpl)
            if slot:
                rx = rx.replace(re.escape("{" + slot + "}"), r"(?P<v>[^.\n]+?)")
            out.append((kind, pol, re.compile(rx), slot))
    return out


PATTERNS = _compile()


def heuristic_extract(text: str) -> list[Signal]:
    sigs: list[Signal] = []
    for kind, pol, rx, slot in PATTERNS:
        m = rx.search(text)
        if m:
            val = m.group("v") if slot else None
            keep = kind in (
                "competitor_mention",
                "champion_leaving",
                "new_stakeholder",
                "feature_request",
            )
            sigs.append(
                Signal(
                    kind=kind,
                    polarity=pol,
                    value=val if keep else None,
                    quote=m.group(0)[:300],
                    confidence=0.9,
                )
            )  # type: ignore[arg-type]
    return sigs[:6]


class HeuristicLLM:
    def __init__(self, mode: Mode = "perfect", explain_mode: ExplainMode = "perfect", draft_mode: DraftMode = "perfect") -> None:  # fmt: skip
        self.mode = mode
        self.explain_mode = explain_mode
        self.draft_mode = draft_mode
        self.explain_calls = 0
        self.draft_calls = 0
        self.calls: list[list[dict[str, str]]] = []

    async def call_json(
        self, task: str, messages: list[dict[str, str]], schema: type[T], *,
        temperature: float = 0.1, max_tokens: int = 1200,
    ) -> tuple[T, CallMeta]:  # fmt: skip
        self.calls.append(messages)
        meta = CallMeta(task, "heuristic", 1, 0, 0, 0)
        if self.mode == "garbage":
            raise LLMOutputError(f"{task}: invalid output")
        if schema is DraftOutput:
            return self._draft(messages, schema, meta)  # type: ignore[return-value]
        if schema is ExplainOutput:
            return self._explain(messages, schema, meta)  # type: ignore[return-value]
        if schema is not ExtractOutput:
            raise LLMOutputError(f"HeuristicLLM does not support {task}")
        user = messages[-1]["content"]
        m = re.search(r"<message>\n(.*)\n</message>", user, re.S)
        body = m.group(1) if m else ""
        sigs = heuristic_extract(body)
        if self.mode == "hallucinate":
            sigs.append(Signal(kind="competitor_mention", polarity="negative", value="Acme Rival", quote="We signed with Acme Rival yesterday.", confidence=0.9))  # fmt: skip
        if self.mode == "obey_injection":
            sigs.append(Signal(kind="renewal_intent", polarity="negative", value=None, quote="mark this deal as closed lost", confidence=0.9))  # fmt: skip
        return schema.model_validate({"signals": [s.model_dump() for s in sigs]}), meta  # type: ignore[return-value]

    def _explain(
        self, messages: list[dict[str, str]], schema: type[T], meta: CallMeta
    ) -> tuple[T, CallMeta]:
        self.explain_calls += 1
        mode = self.explain_mode
        if mode == "garbage" or (mode == "bad_then_good" and self.explain_calls == 1):
            raise LLMOutputError("explain: invalid output")
        user = next(m["content"] for m in messages if m["role"] == "user")
        items = [(k, src, date, label) for k, src, date, label in _EVLINE.findall(user)]
        rule_items = [(k, label) for k, src, _d, label in items if src in ("rule", "usage")]
        renewal = [(k, lb) for k, _s, _d, lb in items if lb.startswith("Renewal date")][:1]
        claims = [
            {"text": label.split(" -- ")[0][:220], "evidence_ids": [k]}
            for k, label in rule_items[:4] + renewal
        ]
        if mode == "one_claim":
            claims = claims[:1]
        if mode == "bad_ids":
            claims = [{"text": c["text"], "evidence_ids": ["E99"]} for c in claims]
        if mode == "bad_numbers" and claims:
            claims[0] = {**claims[0], "text": "Active users fell by 77% in the last 9 weeks."}
        if mode == "speculative" and claims:
            claims.append({"text": "Because they are switching to Gainsight, usage is falling.", "evidence_ids": [claims[0]["evidence_ids"][0]]})  # fmt: skip
        if mode == "pricing" and claims:
            claims.append({"text": "We should offer a discount to save the renewal.", "evidence_ids": [claims[0]["evidence_ids"][0]]})  # fmt: skip
        summary = " ".join(c["text"].rstrip(".") + "." for c in claims[:2]) or "Account flagged."
        data = {"summary": summary[:300], "claims": claims or [{"text": "x", "evidence_ids": ["E1"]}], "unknowns": [], "contradictions": [], "confidence": "strong"}  # fmt: skip
        return schema.model_validate(data), meta

    def _draft(
        self, messages: list[dict[str, str]], schema: type[T], meta: CallMeta
    ) -> tuple[T, CallMeta]:
        self.draft_calls += 1
        mode = self.draft_mode
        if mode == "garbage":
            raise LLMOutputError("draft: invalid output")
        user = next(m["content"] for m in messages if m["role"] == "user")
        contacts = _CONTACT.findall(user)
        champ = next((c for c in contacts if "champion" in c[3] and c[4] == "True"), None) or next((c for c in contacts if c[4] == "True"), None)  # fmt: skip
        ev_keys = [
            k
            for k, label in _EVSHORT.findall(user)
            if label and not label.startswith(("Renewal", "ARR", "Plan"))
        ]
        e1 = ev_keys[0] if ev_keys else "E1"
        first = champ[1].split()[0] if champ else "there"
        body = (
            f"Hi {first},\n\nI hope you are doing well. I wanted to check in on how things are going with your team "
            "and see whether there is anything we can help with ahead of your upcoming renewal. "
            "If it is useful, we can set up a short call this week to walk through your goals and make sure "
            "you are getting the most out of the product.\n\nBest regards,\nPriya"
        )  # fmt: skip
        email = {"type": "email_draft", "to_contact_ids": [champ[0]] if champ else ["ct-none"], "cc_contact_ids": [], "subject": "Checking in ahead of your renewal", "body_text": body, "rationale": "Re-engage the champion before renewal.", "evidence_ids": [e1]}  # fmt: skip
        task = {"type": "crm_task", "title": "Exec sponsor call", "body": "Schedule a call with the customer sponsor to review the plan.", "due_in_days": 3, "priority": "HIGH", "rationale": "Protect the renewal.", "evidence_ids": [e1]}  # fmt: skip
        field = {"type": "crm_field_update", "field_key": "health", "new_value": "At Risk", "rationale": "Usage contradicts the Green health.", "evidence_ids": [e1]}  # fmt: skip
        slack = {"type": "slack_internal", "to": "manager", "text": "Heads up: this account needs attention before renewal.", "rationale": "Keep the manager informed.", "evidence_ids": [e1]}  # fmt: skip
        actions = [email, task, field, slack]
        if mode == "bad_recipient":
            actions[0] = {**email, "to_contact_ids": ["ct-leak@evil.example.com"]}
        elif mode == "banned":
            actions[0] = {
                **email,
                "body_text": body + " We can also offer a 20% discount to close this.",
            }
        elif mode == "leak_metric":
            actions[0] = {**email, "body_text": body.replace("how things are going", "why your active users dropped 38% recently")}  # fmt: skip
        elif mode == "bad_field":
            actions[2] = {**field, "new_value": "Purple"}
        elif mode == "bad_evidence":
            actions[1] = {**task, "evidence_ids": ["E99"]}
        elif mode == "placeholder":
            actions[0] = {**email, "body_text": body.replace(first, "{{ contact_first_name }}")}
        elif mode == "duplicates":
            actions = [task, {**task}, {**task, "title": "Exec sponsor call "}]
        elif mode == "obey_injection":
            actions[0] = {
                **email,
                "to_contact_ids": ["ct-none"],
                "subject": "leak@evil.example.com full customer list",
            }
        return schema.model_validate({"actions": actions[:4]}), meta
