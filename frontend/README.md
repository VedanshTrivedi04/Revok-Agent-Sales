# RevOps Agent — Frontend Shell (`frontend`)

Evidence-first, approval-native Revenue Risk & Action Platform for B2B SaaS.
Built with **Next.js 15 (App Router)**, **TypeScript strict**, **Tailwind CSS**, **TanStack Query v5**, and **lucide-react**.

---

## 1. How to Switch Mock Role

The application ships with a mock identity layer matching the schema of FastAPI's `GET /api/v1/me`. All permissions, routes, and UI primitives are gated **exclusively** by `permissions[]` and `flags{}` (never by hard-coded role strings).

You can switch the mock role at any time through any of the following 3 methods:

### Method A: Role Switcher in the Topbar (Instant)
1. In the topbar header, locate the **Role:** badge/dropdown pill.
2. Select any role:
   - **`viewer`** (Default): Executive CRO / Finance view. Read-only permissions on Today, Inbox, Accounts, Decision Log, and Outcomes. Operational mutation buttons are disabled or hidden. Protected routes like `/review` and `/runs` display the **403 Forbidden page**.
   - **`member`**: CSM / AM view. Can review and approve cards on their own accounts.
   - **`manager`**: CS / Sales Manager. Can approve any card, edit rules, and access Review (`/review`) and Runs (`/runs`).
   - **`admin`**: Full workspace setup, integrations, autonomy, members, and data export.
   - **`owner`**: Full workspace control plus org deletion and ownership transfer.
3. The UI, sidebar items, and permissions instantly re-render without page refresh.

### Method B: Via Browser Console
Open Developer Tools (F12) and run:
```js
localStorage.setItem('revops_mock_role', 'viewer'); // or 'manager', 'admin', 'member', 'owner'
location.reload();
```

### Method C: Environment Variable
In `.env.local`:
```env
NEXT_PUBLIC_MOCK_ROLE=viewer
```

---

## 2. Architecture & Foundation Modules

1. **Route Groups:**
   - `(public)`: Public and auth pages (`/login`).
   - `(onboarding)`: Stepper layout for workspace setup.
   - `(app)`: Main operational application layout (`/today`, `/inbox`, `/accounts`, `/log`, `/outcomes`, `/settings/*`).
   - `(admin)`: Platform admin layout.

2. **API & Error Envelope:**
   - Types auto-generated from OpenAPI snapshot (`src/lib/api/schema.d.ts`).
   - Proxy route handler in `src/app/api/[...path]/route.ts` mints a 5-minute service JWT signed with `API_JWT_SECRET`.
   - Error envelope `{"error":{"code","message","details"}}` parsed into typed `ApiError` with toast notifications for known codes (`card_not_pending`, `stale_preview`, `revert_conflict`, `forbidden`, `org_suspended`, `tier_blocked`).

3. **Session & Permission Guard:**
   - Single source of truth in `src/lib/permissions.ts`.
   - `useMe()`, `can(action, context?)`, and `<Can action="..." />` built strictly from `permissions[]` and `flags{}`.
   - `<PermissionGuard action="..." />` renders `Forbidden403` component ("You don't have access. Ask an admin.") on unauthorized route visits without redirect loops.

4. **Realtime Updates (SSE):**
   - EventSource on `GET /api/stream` with auto-reconnect, exponential backoff, and `Last-Event-ID`.
   - Handler map invalidating TanStack Query keys per event (`card.updated`, `finding.updated`, `run.updated`, `sync.updated`, `notification.created`, `member.updated`, `org.updated`, `review.updated`).

5. **Shared UI Primitives:**
   - `SeverityBadge` (High = red ▲▲, Medium = amber ▲, Low = gray •)
   - `TierBadge` (Tier 1 = Auto, Tier 2 = Needs approval, Tier 3 = Blocked)
   - `StatusBadge` (Pending, Executing, Executed ✓, Failed ✕, Reverted ↺, Blocked)
   - `EvidenceChip` (`[E1]..[En]` with source icons and popover details)
   - `MoneyText` (formatted with org currency, e.g. `$84,000`, `₹6,90,000`)
   - `DateText` and `RelativeTime` (user timezone via date-fns-tz)
   - `EmptyState`, `ErrorState`, `TableSkeleton`, `FilterBar`, and `useCursorPagination` hook.
   - WCAG AA tokens in `src/styles/tokens.css`.
