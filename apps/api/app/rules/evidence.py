"""Deterministic Evidence builder E1..En with cap 15 per algorithm.md section 8 (R3-04)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.rules.base import RuleHit
from app.rules.texts import format_rule_text
from app.services.context import AccountContext


@dataclass
class EvidenceItem:
    evidence_key: str
    kind: str
    ref_id: UUID | None
    label: str
    detail: str | None = None
    source: str | None = None
    source_url: str | None = None
    occurred_at: datetime | None = None


def build_evidence(
    ctx: AccountContext,
    hits: list[RuleHit],
    contradictions: list[dict[str, Any]] | None = None,
) -> list[EvidenceItem]:
    """Select and number evidence items E1..En (capped at 15) strictly per algorithm.md section 8."""
    raw_items: list[dict[str, Any]] = []

    # 1. Account facts (renewal, ARR, plan, seats) -> kind account_field
    account_facts_label = (
        f"Account facts: ARR ${ctx.arr:,.0f}, Plan '{ctx.plan_name or 'Standard'}', "
        f"{ctx.seats_purchased} seats"
    )
    if ctx.renewal_date:
        account_facts_label += f", Renewal {ctx.renewal_date.isoformat()} ({ctx.renewal_in_days}d)"

    raw_items.append(
        {
            "kind": "account_field",
            "ref_id": ctx.account_id,
            "label": account_facts_label,
            "detail": f"CRM health: {ctx.crm_health or 'unspecified'}",
            "source": "hubspot",
            "occurred_at": ctx.now,
        }
    )

    # 2. Rule metrics sorted by points desc
    sorted_hits = sorted(hits, key=lambda h: h.severity_points, reverse=True)
    for h in sorted_hits:
        metric_label = format_rule_text(h.rule_key, h.metrics)
        raw_items.append(
            {
                "kind": "rule_metric",
                "ref_id": None,
                "label": f"Metric ({h.rule_key}): {metric_label}",
                "detail": str(h.metrics),
                "source": "revops",
                "occurred_at": ctx.now,
            }
        )

        # Also include evidence refs for this hit
        for ref in h.evidence_refs:
            for rid in ref.ref_ids[:2]:  # at most 2 per ref
                raw_items.append(
                    {
                        "kind": ref.kind,
                        "ref_id": rid,
                        "label": f"Supporting {ref.kind} record",
                        "detail": f"Reference ID: {rid}",
                        "source": "hubspot" if ref.kind in ("deal", "contact") else "usage" if ref.kind == "usage" else "revops",
                        "occurred_at": ctx.now,
                    }
                )

    def _parse_dt(val: Any) -> datetime:
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except Exception:
                return ctx.now
        return ctx.now

    # 3. Signals (30d) sorted by confidence desc (max 4)
    sorted_signals = sorted(
        ctx.signals_30d,
        key=lambda s: float(s.get("confidence", 0.0)),
        reverse=True,
    )[:4]
    for sig in sorted_signals:
        sig_id = UUID(str(sig["id"])) if sig.get("id") else None
        quote = sig.get("quote") or "Detected signal"
        kind = sig.get("kind") or "signal"
        conf = float(sig.get("confidence", 0.0))
        raw_items.append(
            {
                "kind": "signal",
                "ref_id": sig_id,
                "label": f'Signal ({kind}, conf {conf:.2f}): "{quote[:100]}"',
                "detail": str(sig.get("value") or {}),
                "source": "signal",
                "occurred_at": _parse_dt(sig.get("created_at") or sig.get("detected_at")),
            }
        )

    # 4. Contradictions (max 3)
    for contra in (contradictions or [])[:3]:
        raw_items.append(
            {
                "kind": "account_field",
                "ref_id": None,
                "label": f"Contradiction: {contra.get('text', '')}",
                "detail": "Flagged by deterministic contradiction detector",
                "source": "revops",
                "occurred_at": ctx.now,
            }
        )

    # 5. Open deals (max 2)
    for deal in ctx.open_deals[:2]:
        deal_id = None
        if deal.get("id"):
            try:
                deal_id = UUID(str(deal["id"]))
            except (ValueError, TypeError):
                deal_id = None
        deal_name = deal.get("name") or "Open Deal"
        stage = deal.get("stage") or "open"
        amount = deal.get("amount")
        amount_str = f" (${amount:,.0f})" if amount else ""
        raw_items.append(
            {
                "kind": "deal",
                "ref_id": deal_id,
                "label": f"Open Deal: '{deal_name}' in stage '{stage}'{amount_str}",
                "detail": f"Next step: {deal.get('next_step') or 'None'}",
                "source": "hubspot",
                "occurred_at": ctx.now,
            }
        )

    # Deduplicate by (kind, ref_id) or label, capped at 15
    seen_keys: set[str] = set()
    deduped: list[dict[str, Any]] = []

    for item in raw_items:
        key = f"{item['kind']}:{item['ref_id']}:{item['label']}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(item)
        if len(deduped) >= 15:
            break

    # Number sequentially as E1..En
    numbered_evidence: list[EvidenceItem] = []
    for idx, item in enumerate(deduped, start=1):
        numbered_evidence.append(
            EvidenceItem(
                evidence_key=f"E{idx}",
                kind=item["kind"],
                ref_id=item["ref_id"],
                label=item["label"],
                detail=item.get("detail"),
                source=item.get("source"),
                source_url=item.get("source_url"),
                occurred_at=_parse_dt(item.get("occurred_at")),
            )
        )

    return numbered_evidence
