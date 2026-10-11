---
description: Strict requirement to never use hardcoded, fake, or dummy data in the frontend. All data must be fetched dynamically from the FastAPI backend.
globs: ["frontend/**/*", "apps/web/**/*"]
---

# No Hardcoded Data — All Frontend Data Must Be Dynamic

## Core Rule
**NEVER use hardcoded, fake, synthetic, or dummy data anywhere in the frontend.** Every single piece of state, account metrics, user identity, organization information, action cards, findings, timelines, audit logs, and integrations must be fetched dynamically from the FastAPI backend.

## Specific Mandates

1. **No Fake User/Org Names or Fallbacks:**
   - Never use placeholder identities like `"Marcus Vance"`, `"Acme SaaS"`, or `"finance.cro@acmesaas.com"`.
   - If data is loading, render standard loading skeletons (`TableSkeleton`, pulsating placeholders, or `"Loading..."`).
   - If data is empty or missing, render a dash (`—`) or an `<EmptyState>` component.
   - If an API request fails, render an `<ErrorState>` component with a retry button.

2. **No Mock Data Generators in Route Handlers:**
   - Next.js route handlers (`src/app/api/[...path]/route.ts`, `src/app/api/stream/route.ts`) must strictly act as a transparent proxy to the FastAPI backend (`${NEXT_PUBLIC_API_BASE}/api/v1/*`).
   - Route handlers must **NEVER** construct hardcoded mock response objects (`mockUser`, `mockOrg`, fake lists, synthetic heartbeats).
   - If the backend is unreachable or returns an HTTP error, propagate the error or return a typed `503 backend_unavailable` error envelope so the UI can accurately present the error state.

3. **Dynamic Integrations & Alerts:**
   - Banners and health alerts (e.g. `IntegrationBanner`) must fetch current status from `/integrations` rather than receiving hardcoded props like `hasError={false}` or `providerName="HubSpot"`.

4. **Strict Schema Derivation:**
   - All response types must be imported directly from the generated OpenAPI schema (`src/lib/api/schema.d.ts`).
   - Do not write manual fake types or fabricate payload shapes.
