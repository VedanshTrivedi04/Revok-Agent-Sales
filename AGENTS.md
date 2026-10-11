# RevOps Agent — Workspace Rules

## 1. No Hardcoded, Dummy, or Fake Data in Frontend
- **Zero Dummy Data**: Never hardcode names, organization titles, dummy accounts, synthetic metrics, or fake lists anywhere in the frontend codebase (`frontend/` or `apps/web/`).
- **All Data from FastAPI Backend**: Every component, table, card, metric, badge, and user session must be fetched dynamically from the FastAPI backend at `NEXT_PUBLIC_API_BASE`.
- **Transparent API Proxies**: Next.js route handlers (`src/app/api/[...path]/route.ts` and `src/app/api/stream/route.ts`) are transparent proxies minting a 5-minute service JWT and forwarding requests directly to FastAPI `/api/v1/*`. They must NEVER return synthetic mock fallbacks.
- **Accurate State Rendering**:
  - While fetching: Render `TableSkeleton` or skeleton loaders.
  - When empty: Render `<EmptyState title="..." description="..." />` or a dash (`—`).
  - When error occurs: Render `<ErrorState title="..." message="..." onRetry={refetch} />`.

## 2. Permission and Role System
- All navigation gating, UI button visibility, and route protection must be strictly based on `permissions[]` and `flags{}` returned by `GET /api/v1/me`.
- Never check role strings (like `role === "viewer"`) to gate actions or render UI.
- Use `useMe()`, `can(action, context)`, and `<Can action="...">` for permission checks.
