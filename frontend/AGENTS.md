<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

## Frontend Architecture Rules: 100% Dynamic Backend Data
1. **Zero Hardcoded/Fake Data**: Never use hardcoded strings, dummy identities (e.g. "Marcus Vance", "Acme SaaS"), synthetic lists, or dummy mock objects in frontend components or Next.js route handlers.
2. **Transparent Backend Proxy**: All Next route handlers in `/api/[...path]` and `/api/stream` must strictly proxy requests to the FastAPI backend (`process.env.NEXT_PUBLIC_API_BASE`).
3. **State Handling**: If data is loading, render `TableSkeleton` or pulsating skeleton loaders. If empty, render `<EmptyState>`. If backend is down or errors, render `<ErrorState>` with a retry trigger.
4. **Permissions & Roles**: Gate UI elements exclusively with `can(action)` built from `permissions[]` and `flags{}` returned dynamically by `GET /me`. Never inspect role strings.

