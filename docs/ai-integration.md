# AI Integration Guide (`docs/ai-integration.md`)

> Comprehensive specification for integrating external AI services with the RevOps platform via `/internal/v1/orgs/{org}/...`.
> Target audience: AI Engineers, MLOps, and Service Integrators.

---

## 1. Architecture & Security Principles

1. **Service-to-Service Authentication:**
   Every internal endpoint requires the `X-Internal-Key` header matching the platform's configured `INTERNAL_API_KEY`.
   Requests without or with an invalid key receive `401 unauthenticated`.

2. **Tenant Isolation:**
   All routes are tenant-scoped under `/internal/v1/orgs/{org}/...`. The backend automatically applies PostgreSQL Row Level Security (RLS) within each request's transaction session.

3. **Untrusted Data Model:**
   Customer content (email bodies, notes) travels as raw data, never system instructions. The backend performs strict server-side validation on all incoming AI responses before persistence.

4. **Deterministic Validation Rules:**
   - **Signal Quotes:** Every quoted snippet must be an exact substring of the referenced event text.
   - **Evidence Citations:** Every evidence ID (`E1`, `E2`, ...) cited in claims or contradictions must exist for that specific finding.
   - **Recipient Allowlists:** Action proposals for email drafts must only address verified account contacts or org internal domains.
   - **Banned Phrases:** Hard guarantees, refund promises, or unapproved discounts are strictly blocked server-side.
   - **Autonomy Policy:** Tier 3 action types are rejected server-side (`tier_blocked`).

---

## 2. API Endpoints Reference

Base path: `/internal/v1/orgs/{org}`

### 2.1 Fetch Account Context
`GET /accounts/{account_id}/context`

Retrieves complete account context, timeline events, signals, rule hits, and backend-numbered evidence items (`E1`, `E2`, ...).

**Request Headers:**
```http
X-Internal-Key: <secret>
```

**Response (200 OK):**
```json
{
  "account": {
    "id": "c1f7a8b9-1234-4567-890a-bcdef0123456",
    "name": "Acme SaaS",
    "domains": ["acme.com"],
    "arr": 150000.0,
    "plan_name": "Enterprise",
    "seats_purchased": 100,
    "renewal_date": "2026-12-01",
    "lifecycle_stage": "customer",
    "crm_health": "Amber",
    "status": "active",
    "risk_level": "medium",
    "priority_score": 75.0,
    "crm_url": "https://app.hubspot.com/contacts/123/company/456"
  },
  "contacts": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "name": "Sarah Connor",
      "email": "sarah@acme.com",
      "title": "Director of Engineering",
      "role_tags": ["champion", "decision_maker"],
      "is_active": true
    }
  ],
  "deals": [],
  "usage": [
    {
      "id": "99887766-5544-3322-1100-aabbccddeeff",
      "period_start": "2026-10-01",
      "period_end": "2026-10-07",
      "active_users": 62,
      "seats_used": 62
    }
  ],
  "recent_events": [
    {
      "id": "55443322-1100-aabb-ccdd-eeff00112233",
      "account_id": "c1f7a8b9-1234-4567-890a-bcdef0123456",
      "type": "email_in",
      "occurred_at": "2026-10-08T14:22:00Z",
      "title": "Renewal inquiry",
      "text": "We are evaluating alternate vendors who offer 30% lower prices."
    }
  ],
  "signals": [],
  "rule_hits": [
    {
      "id": "11223344-5566-7788-9900-aabbccddeeff",
      "rule_key": "R01",
      "category": "usage",
      "finding_type": "risk",
      "severity_points": 35,
      "metrics": {"drop_pct": 38.0}
    }
  ],
  "evidence": [
    {
      "key": "E1",
      "kind": "usage",
      "label": "Weekly active users dropped by 38%",
      "detail": "Active users dropped from 100 to 62",
      "source": "usage",
      "source_url": null,
      "occurred_at": "2026-10-07T00:00:00Z"
    }
  ],
  "missing_data": []
}
```

---

### 2.2 Ingest Extracted Signals
`POST /events/{event_id}/signals`

Saves structured signals extracted from communication text. Quotes are validated against event text.

**Request Body:**
```json
{
  "signals": [
    {
      "kind": "competitor_mention",
      "polarity": "negative",
      "value": {"competitor": "VendorX"},
      "confidence": 0.95,
      "quote": "evaluating alternate vendors who offer 30% lower prices",
      "model": "qwen3.5-9b",
      "prompt_version": "extract@1.0.0"
    }
  ]
}
```

**Response (200 OK):**
```json
{
  "saved": 1,
  "rejected": []
}
```

If a quote does not match:
```json
{
  "saved": 0,
  "rejected": [
    {
      "quote": "we are canceling immediately",
      "reason": "quote must be a substring of the event text"
    }
  ]
}
```

---

### 2.3 Save Explanation
`POST /findings/{finding_id}/explanation`

Saves natural language explanation and fact claims. All evidence IDs must exist for the finding.

**Request Body:**
```json
{
  "summary": "Active usage decreased by 38% while customer is evaluating competitors.",
  "claims": [
    {
      "text": "Active users dropped from 100 to 62 in the last 7 days.",
      "evidence_ids": ["E1"]
    }
  ],
  "unknowns": ["Whether the champion has already scheduled vendor demos"],
  "contradictions": [],
  "confidence_label": "high",
  "model": "qwen3.5-9b",
  "prompt_version": "explain@1.0.0"
}
```

**Response (200 OK):**
```json
{
  "finding_id": "f1e2d3c4-b5a6-7890-abcd-ef1234567890",
  "accepted": true,
  "errors": []
}
```

---

### 2.4 Save Action Proposals
`POST /findings/{finding_id}/proposals`

Generates actionable next steps (drafts, tasks, notes). Validated against recipient allowlists, banned phrases, and policy tiers.

**Request Body:**
```json
{
  "proposals": [
    {
      "type": "email_draft",
      "payload": {
        "to": ["sarah@acme.com"],
        "subject": "Quick check-in on your team's rollout",
        "body": "Hi Sarah, I wanted to see if we could connect this week regarding your roadmap."
      },
      "rationale": "Re-engage champion before renewal window closes.",
      "evidence_keys": ["E1"]
    },
    {
      "type": "crm_task",
      "payload": {
        "title": "Review Acme competitor threat with account team",
        "due_date": "2026-10-18",
        "priority": "HIGH"
      },
      "rationale": "Internal sync on pricing strategy.",
      "evidence_keys": ["E1"]
    }
  ]
}
```

**Response (200 OK):**
```json
{
  "created_card_ids": [
    "c1a2b3c4-d5e6-7890-1234-567890abcdef",
    "d2e3f4a5-b6c7-8901-2345-678901bcdefa"
  ],
  "rejected": []
}
```

---

## 3. Python Integration Client Example

```python
"""Example Python client for RevOps internal AI integration."""

import httpx
from typing import Any
from uuid import UUID


class RevOpsAIClient:
    def __init__(self, base_url: str, internal_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "X-Internal-Key": internal_key,
            "Content-Type": "application/json",
        }

    async def get_context(self, org_id: UUID, account_id: UUID) -> dict[str, Any]:
        url = f"{self.base_url}/internal/v1/orgs/{org_id}/accounts/{account_id}/context"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers, timeout=10.0)
            resp.raise_for_status()
            return resp.json()

    async def save_signals(self, org_id: UUID, event_id: UUID, signals: list[dict[str, Any]]) -> dict[str, Any]:
        url = f"{self.base_url}/internal/v1/orgs/{org_id}/events/{event_id}/signals"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self.headers, json={"signals": signals})
            resp.raise_for_status()
            return resp.json()

    async def save_explanation(self, org_id: UUID, finding_id: UUID, explanation: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/internal/v1/orgs/{org_id}/findings/{finding_id}/explanation"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self.headers, json=explanation)
            resp.raise_for_status()
            return resp.json()

    async def save_proposals(self, org_id: UUID, finding_id: UUID, proposals: list[dict[str, Any]]) -> dict[str, Any]:
        url = f"{self.base_url}/internal/v1/orgs/{org_id}/findings/{finding_id}/proposals"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self.headers, json={"proposals": proposals})
            resp.raise_for_status()
            return resp.json()
```
