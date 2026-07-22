<!-- last_verified: 2026-07-14 -->
# Feature: Admin console

## Purpose
Give an admin cross-user visibility over every resource in the workspace (users,
subscriptions, generation jobs, files, provider usage) plus one audited action —
changing a user's role.

## Used By
- UI: `/admin` page (role-gated), sidebar "Admin" entry (shown only to admins)
- API: `GET /admin/overview|users|subscriptions|jobs|files|provider-runs|audit`,
  `POST /admin/users/{user_id}/role`
- DB: `public.admin_audit_events` (+ the profiles/roles GRANT backfill)

## Core Functions
- `apps/web/src/app/(app)/admin/page.tsx` — role guard (UX; API is the real gate)
- `apps/web/src/components/admin/admin-console.tsx` — tabbed console shell
- `apps/web/src/components/admin/overview-cards.tsx` — aggregate KPI cards
- `apps/web/src/components/admin/grids.tsx` — the six sortable/filterable DataGrids
- `services/api/app/runtime/admin.py` — routes, all behind `require_admin`
- `services/api/app/service/admin.py` — overview aggregation + audited role change
- `services/api/app/repo/supabase_admin.py` — service-role reads, count, audit insert
- `services/api/app/runtime/auth.py` — `require_admin` dependency

## Canonical Files
- Admin route pattern: `services/api/app/runtime/admin.py`
- DataGrid pattern: `apps/web/src/components/admin/grids.tsx` (built on `ui/data-table.tsx`)

## Inputs
- Bearer token (Supabase session) — must resolve to a profile with `role = 'admin'`
- Role change: `{ role: 'user' | 'admin' }` (path `user_id`)

## Outputs
- `GET /admin/overview` → `AdminOverview` (users, admins, active_subscriptions,
  generation_jobs, failed_jobs, files, storage_bytes, provider_runs, webhook_events)
- `GET /admin/users` → `AdminUser[]`, `/subscriptions` → `Subscription[]`,
  `/jobs` → `GenerationJob[]`, `/files` → `AdminFile[]`,
  `/provider-runs` → `AdminProviderRun[]`, `/audit` → `AdminAuditEvent[]`
- `POST /admin/users/{id}/role` → `AdminUser`; side effect: one
  `admin_audit_events` row (service-role insert)

## Flow
- Reads use the service-role key (they span all users' rows, bypassing RLS) and
  only run behind `require_admin` (401 signed-out, 403 non-admin).
- The role change is issued with the **caller's own token**, not the service
  role: `public.profiles` has a `prevent_role_escalation` trigger that checks
  `is_admin()` against `auth.uid()`, so a service-role PATCH would be rejected.
- After a successful role change the service appends an audit row and the UI
  invalidates the users / audit / overview caches.

## Edge Cases
- Non-admin hits any `/admin/*` → 403 (server); the `/admin` page also redirects.
- Role change for a missing user → 404.
- Invalid role value → 422 (Pydantic `^(user|admin)$`).
- An admin cannot change their **own** role in the grid (self-lockout guard, UI).
- Table grants matter: without `GRANT SELECT ON public.profiles` (in the init
  schema), role reads would 403 at the grant layer and silently fall back to
  `'user'` — which would make the whole admin surface unreachable.

## UX States
- Loading: skeleton rows per grid; skeleton stat cards on overview
- Empty: per-grid empty state (e.g. "No admin actions recorded yet")
- Error: inline `ErrorState` with retry
- Filter: each grid has a global-filter search box; all columns sortable + paged

## Verification
- Test files: `services/api/tests/test_admin.py`
- Required cases: 401 without token, 403 for non-admin, overview shape, each list,
  audited role change, 404 missing user, 422 invalid role
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure && pnpm build`
- Pass criteria: all pytest green, ruff/eslint clean, `next build` succeeds

## Related Docs
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [Billing](billing.md)
- [Generation](generation.md)
- [App Workflows](../app-workflows.md)
