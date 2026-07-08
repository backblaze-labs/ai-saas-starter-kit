-- Generation foundation for the SaaS starter: the AI media-generation slice.
-- A generation job (one text-to-image run), the generated files it produced
-- (tracked in Postgres in addition to living in B2, so dashboards/DataGrids can
-- query them), a provider-run provenance row per external invocation, and a
-- usage-events meter. All rows are written ONLY by the server via the service
-- role (the generation service already holds the validated user id); the browser
-- never writes here. Reads are RLS-scoped to the owner (admins see all).
--
-- The B2 bucket remains the source of truth for the bytes; `public.files` mirrors
-- the object key + provenance so the app can list/paginate a user's generations
-- without a bucket scan per request.
--
-- Reuses public.set_updated_at() and public.is_admin() from the auth migration.

-- ---------------------------------------------------------------------------
-- Generation jobs (one text-to-image run)
-- ---------------------------------------------------------------------------
create table if not exists public.generation_jobs (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users (id) on delete cascade,
  prompt         text not null,
  provider       text not null default 'nvidia',
  model          text not null,
  status         text not null default 'running',   -- running|succeeded|failed
  error          text,
  seed           bigint,
  run_id         text,                               -- Genblaze run id
  manifest_uri   text,                               -- B2 URI of the SHA-256 manifest
  canonical_hash text,                               -- manifest canonical hash
  cost_usd       numeric,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create index if not exists generation_jobs_user_idx
  on public.generation_jobs (user_id, created_at desc);

comment on table public.generation_jobs is
  'One AI image-generation run. Written server-side only (service role); the browser reads its own rows via RLS.';

create trigger generation_jobs_set_updated_at
  before update on public.generation_jobs
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Generated files (mirror of the B2 objects a job produced)
-- ---------------------------------------------------------------------------
create table if not exists public.files (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users (id) on delete cascade,
  job_id      uuid references public.generation_jobs (id) on delete cascade,
  b2_key      text not null,
  url         text,                                  -- durable (non-presigned) B2 URL
  sha256      text,
  media_type  text,
  size_bytes  bigint,
  width       int,
  height      int,
  created_at  timestamptz not null default now()
);

create unique index if not exists files_b2_key_key on public.files (b2_key);
create index if not exists files_user_idx on public.files (user_id, created_at desc);
create index if not exists files_job_idx on public.files (job_id);

comment on table public.files is
  'Postgres mirror of generated B2 objects (key + provenance). The bucket is the source of truth for bytes; this makes a user''s generations queryable without a bucket scan.';

-- ---------------------------------------------------------------------------
-- Provider runs (one row per external provider invocation — provenance)
-- ---------------------------------------------------------------------------
create table if not exists public.provider_runs (
  id           uuid primary key default gen_random_uuid(),
  job_id       uuid not null references public.generation_jobs (id) on delete cascade,
  provider     text not null,
  model        text not null,
  run_id       text,
  status       text not null,
  cost_usd     numeric,
  assets_count int not null default 0,
  created_at   timestamptz not null default now()
);

create index if not exists provider_runs_job_idx on public.provider_runs (job_id);

comment on table public.provider_runs is
  'One row per external generation-provider invocation (observability / provenance). Service role only.';

-- ---------------------------------------------------------------------------
-- Usage events (metering — one row per billable unit)
-- ---------------------------------------------------------------------------
create table if not exists public.usage_events (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  job_id     uuid references public.generation_jobs (id) on delete set null,
  kind       text not null default 'image_generation',
  units      int not null default 1,
  cost_usd   numeric,
  created_at timestamptz not null default now()
);

create index if not exists usage_events_user_idx on public.usage_events (user_id, created_at desc);

comment on table public.usage_events is
  'Metering log: one row per billable generation unit, for per-user usage aggregation on the dashboard/admin. Service role only.';

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
alter table public.generation_jobs enable row level security;
alter table public.files           enable row level security;
alter table public.provider_runs   enable row level security;
alter table public.usage_events    enable row level security;

-- generation_jobs: a user reads their own jobs; admins read all. All writes go
-- through the service role (which bypasses RLS) — no client write policies.
create policy "generation_jobs_select_own"
  on public.generation_jobs for select to authenticated
  using (user_id = auth.uid());
create policy "generation_jobs_select_admin"
  on public.generation_jobs for select to authenticated
  using (public.is_admin());

-- files: same ownership model.
create policy "files_select_own"
  on public.files for select to authenticated
  using (user_id = auth.uid());
create policy "files_select_admin"
  on public.files for select to authenticated
  using (public.is_admin());

-- provider_runs: no user_id column — ownership is derived from the parent job.
create policy "provider_runs_select_own"
  on public.provider_runs for select to authenticated
  using (
    exists (
      select 1 from public.generation_jobs j
      where j.id = provider_runs.job_id
        and (j.user_id = auth.uid() or public.is_admin())
    )
  );

-- usage_events: same ownership model as generation_jobs.
create policy "usage_events_select_own"
  on public.usage_events for select to authenticated
  using (user_id = auth.uid());
create policy "usage_events_select_admin"
  on public.usage_events for select to authenticated
  using (public.is_admin());

-- ---------------------------------------------------------------------------
-- Table grants
-- ---------------------------------------------------------------------------
-- RLS decides which ROWS a role sees; table-level GRANTs decide whether a role
-- may touch the table at all. Tables created by `postgres` in a migration only
-- inherit DML grants portably on a well-configured project — so grant explicitly
-- (same portability fix as the billing migration). The generation backend reaches
-- these with the service role; SELECT grants to authenticated make the RLS read
-- policies above reachable for direct client reads.
grant select on public.generation_jobs to authenticated, service_role;
grant insert, update on public.generation_jobs to service_role;

grant select on public.files to authenticated, service_role;
grant insert, update, delete on public.files to service_role;

grant select on public.provider_runs to authenticated, service_role;
grant insert on public.provider_runs to service_role;

grant select on public.usage_events to authenticated, service_role;
grant insert on public.usage_events to service_role;
