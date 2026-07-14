<!-- last_verified: 2026-07-14 -->
# Feature: Dashboard

## Purpose
Give a signed-in user an at-a-glance view of their SaaS state: current plan +
status, storage used, AI generations produced, failed jobs, and recent activity.

## Used By
- UI: `/` page (dashboard home)
- API: `GET /billing/subscription`, `GET /files/stats`,
  `GET /files/stats/activity`, `GET /generation/jobs`

## Core Functions
- `apps/web/src/components/dashboard/saas-stats-cards.tsx` — 4 KPI cards (plan,
  storage, generations, failed jobs), composed from existing query hooks
- `apps/web/src/components/dashboard/recent-generations-table.tsx` — last ~6 jobs
- `apps/web/src/components/dashboard/upload-chart.tsx` — storage activity chart
- `apps/web/src/components/status-badge.tsx` — shared status pill (job/sub/run)
- `apps/web/src/lib/queries.ts` — `useSubscription`, `useFileStats`,
  `useUploadActivity`, `useGenerationJobs`

## Canonical Files
- Dashboard KPI pattern: `apps/web/src/components/dashboard/saas-stats-cards.tsx`
- Recent-activity table pattern: `apps/web/src/components/dashboard/recent-generations-table.tsx`

## Inputs
- None (dashboard loads data automatically for the signed-in user)

## Outputs
- `GET /billing/subscription` → `Subscription` (plan_id + status card)
- `GET /files/stats` → `UploadStats` (storage-used card)
- `GET /generation/jobs` → `GenerationJob[]` (generations count, failed count,
  recent-generations table — no dashboard-specific endpoint needed)
- `GET /files/stats/activity?days=7` → `DailyUploadCount[]` (activity chart)

## Flow
- Page loads → parallel query hooks (subscription, file stats, generation jobs,
  upload activity).
- KPI cards render plan + status badge, storage used, count of succeeded jobs,
  count of failed jobs.
- Recent-generations table shows the newest ~6 jobs with prompt, status badge,
  and created date; links to `/generate`.
- Storage activity chart renders server-aggregated daily counts.

## Edge Cases
- API unavailable → error/loading states; the activity chart does not show a
  false zero while loading.
- No subscription row → treated as the Free tier (status inactive).
- No generations yet → empty state in the recent table; counts show 0.

## UX States
- Loading: skeleton placeholders for cards, table, and chart
- Empty: "No generations yet" in the recent table
- Loaded: populated cards, chart, table

## Verification
- Test files: `services/api/tests/test_generation.py` (jobs feed the cards/table),
  `services/api/tests/test_billing.py`, `services/api/tests/test_upload_activity.py`
- Required cases: subscription present/absent, jobs with mixed statuses, empty
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure && pnpm build`
- Pass criteria: all pytest green, ruff/eslint clean, `next build` succeeds

## Related Docs
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [Admin](admin.md)
- [App Workflows](../app-workflows.md)
