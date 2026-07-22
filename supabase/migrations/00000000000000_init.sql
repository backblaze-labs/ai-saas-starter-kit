-- =============================================================================
-- AI SaaS Starter Kit — database schema (single init)
-- =============================================================================
-- This is the whole schema in one file: auth (roles + profiles + RLS + triggers),
-- billing (plans/subscriptions/stripe_events), generation (jobs/files/provider
-- runs/usage), and the admin audit log. A fresh `supabase db reset` (local) or
-- `supabase db push` (remote) applies it in one pass.
--
-- It is intentionally NOT split into incremental migrations: this repo is a
-- starter you clone and initialise from scratch, so the schema reads best as a
-- coherent whole. When you build on the kit, add your own timestamped migrations
-- alongside this file and treat this init as immutable once you've deployed.
--
-- Grants note (applies to every `grant` below): RLS decides which ROWS a role
-- sees; table-level GRANTs decide whether a role may touch the table at all.
-- Tables created by `postgres` in a migration don't portably inherit DML grants
-- for the API roles (anon/authenticated/service_role) on every instance, so we
-- grant explicitly. Server code reaches these tables with the service role; the
-- SELECT grants to authenticated/anon make the RLS read policies reachable for
-- direct client reads.

-- =============================================================================
-- AUTH — roles, profiles, RLS, triggers
-- =============================================================================
-- Admin is granted deliberately, never automatically: every new signup gets the
-- default 'user' role (see handle_new_user() below). Grant your first admin
-- explicitly — locally or after deploy — with the service role / SQL editor:
--
--   update public.profiles set role = 'admin' where email = 'you@example.com';
--
-- (auto-promoting the first signup would hand admin to the first stranger to
-- register on a public deploy.)

-- Roles catalog ---------------------------------------------------------------
create table if not exists public.roles (
  name        text primary key,
  description text
);

insert into public.roles (name, description) values
  ('user',  'Standard authenticated user'),
  ('admin', 'Administrator with full access to every resource')
on conflict (name) do nothing;

-- Profiles (1:1 with auth.users) ----------------------------------------------
create table if not exists public.profiles (
  id         uuid primary key references auth.users (id) on delete cascade,
  email      text,
  full_name  text,
  avatar_url text,
  role       text not null default 'user' references public.roles (name),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.profiles is 'Public profile + role for each authenticated user; mirrors auth.users.';

-- Helpers ---------------------------------------------------------------------

-- Keep updated_at current on every profile update.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- Is the current authenticated user an admin?
-- SECURITY DEFINER + fixed search_path so RLS policies can call it without
-- recursing into the profiles policies themselves.
create or replace function public.is_admin()
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select exists (
    select 1 from public.profiles
    where id = auth.uid() and role = 'admin'
  );
$$;

-- Auto-create a profile row when a new auth user is inserted, always with the
-- default 'user' role. Admin is granted explicitly (see the section note) so a
-- public deploy never hands admin to the first stranger who registers.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, full_name, avatar_url, role)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'name'),
    new.raw_user_meta_data ->> 'avatar_url',
    'user'
  )
  on conflict (id) do nothing;

  return new;
end;
$$;

-- Block non-admins from changing their own role (privilege escalation guard).
create or replace function public.prevent_role_escalation()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.role is distinct from old.role and not public.is_admin() then
    raise exception 'only admins can change roles';
  end if;
  return new;
end;
$$;

-- Triggers --------------------------------------------------------------------
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

create trigger profiles_prevent_role_escalation
  before update on public.profiles
  for each row execute function public.prevent_role_escalation();

-- Row Level Security ----------------------------------------------------------
alter table public.profiles enable row level security;
alter table public.roles    enable row level security;

-- roles: readable by any authenticated user (small catalog); no client writes.
create policy "roles_read_authenticated"
  on public.roles for select
  to authenticated
  using (true);

-- profiles: read your own row; admins read all.
create policy "profiles_select_own_or_admin"
  on public.profiles for select
  to authenticated
  using (id = auth.uid() or public.is_admin());

-- profiles: update your own row (role changes are gated by the trigger above).
create policy "profiles_update_own"
  on public.profiles for update
  to authenticated
  using (id = auth.uid())
  with check (id = auth.uid());

-- profiles: admins may update any row.
create policy "profiles_update_admin"
  on public.profiles for update
  to authenticated
  using (public.is_admin())
  with check (public.is_admin());

-- Grants (see the grants note at the top) -------------------------------------
grant select on public.roles to anon, authenticated, service_role;
grant select on public.profiles to authenticated, service_role;
-- own-row + admin profile updates are gated by the RLS policies above; the
-- table-level UPDATE grant is what makes those policies reachable.
grant update on public.profiles to authenticated;
grant insert, update, delete on public.profiles to service_role;

-- =============================================================================
-- BILLING — plan catalog, per-user subscription, webhook idempotency log
-- =============================================================================
-- Stripe price IDs are account-specific, so they live in env config
-- (STRIPE_PRICE_PRO / STRIPE_PRICE_TEAM) and are resolved by the backend — they
-- are deliberately NOT stored here, so this catalog is portable across any
-- Stripe account. The subscription row is written ONLY by the Stripe webhook via
-- the service role; the browser never writes it.

-- Plan catalog (display + entitlement metadata) -------------------------------
create table if not exists public.plans (
  id          text primary key,                       -- 'free' | 'pro' | 'team'
  name        text not null,
  rank        int  not null,                          -- ordering + gating comparisons (free<pro<team)
  price_cents int  not null default 0,
  currency    text not null default 'usd',
  interval    text not null default 'month',
  features    jsonb not null default '[]'::jsonb,
  is_public   boolean not null default true,
  created_at  timestamptz not null default now()
);

comment on table public.plans is
  'Subscription plan catalog (display + entitlement metadata). Stripe price IDs are env config, not stored here, so the catalog is Stripe-account portable.';

insert into public.plans (id, name, rank, price_cents, features) values
  ('free', 'Free', 0, 0,
    '["Auth + file manager","1 GB storage","Community support"]'::jsonb),
  ('pro',  'Pro',  1, 1900,
    '["Everything in Free","AI media generation","100 GB storage","Email support"]'::jsonb),
  ('team', 'Team', 2, 4900,
    '["Everything in Pro","Team seats & admin","1 TB storage","Priority support"]'::jsonb)
on conflict (id) do nothing;

-- Subscriptions (one synced row per user; source of truth is Stripe) ----------
create table if not exists public.subscriptions (
  user_id                uuid primary key references auth.users (id) on delete cascade,
  plan_id                text not null default 'free' references public.plans (id),
  status                 text not null default 'inactive',  -- active|trialing|past_due|canceled|incomplete|inactive
  stripe_customer_id     text,
  stripe_subscription_id text,
  current_period_end     timestamptz,
  cancel_at_period_end   boolean not null default false,
  -- Stripe EVENT.created (unix seconds) of the last subscription event applied
  -- to this row. Used to reject out-of-order webhooks: Stripe does not
  -- guarantee ordered delivery, so a stale/retried customer.subscription.*
  -- can arrive after a newer one. NOT the Subscription object's own `created`
  -- (that is constant for the life of the subscription and useless for
  -- ordering). NULL until the first subscription event lands.
  last_event_created_at  bigint,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now()
);

create index if not exists subscriptions_customer_idx
  on public.subscriptions (stripe_customer_id);

comment on table public.subscriptions is
  'Current subscription state per user, synced from Stripe by the webhook (service-role writes only). Absence of a row means the user is on the Free tier.';

create trigger subscriptions_set_updated_at
  before update on public.subscriptions
  for each row execute function public.set_updated_at();

-- Out-of-order-safe subscription upsert ---------------------------------------
-- Stripe does not guarantee ordered webhook delivery, so a stale or retried
-- customer.subscription.* event can arrive AFTER a newer one and overwrite
-- current state with stale data. This function makes the freshness check
-- ATOMIC in the DB (not a read-compare-write in the API, which would race
-- under concurrent webhook deliveries): the ON CONFLICT branch applies only
-- when the incoming event is at least as new as the last one applied to the
-- row. A staler event is silently a no-op.
--
-- p_event_created_at is the Stripe EVENT's `created` (unix seconds). NULL is
-- treated as "cannot order — apply it" so a missing timestamp never drops an
-- update (idempotency is still handled separately by stripe_events). Caveat: a
-- NULL-timestamped event also WRITES NULL back to last_event_created_at,
-- re-disarming the guard until the next non-NULL event lands — harmless for
-- Stripe (event.created is always set) but relevant to any adapter that omits
-- it. Ordering is second-granular, and the comparison is `>=`, so two distinct
-- events in the SAME second are last-delivered-wins (an inherent limit, not a
-- regression — same-second state flips are rare and retries are idempotent).
--
-- Called by the webhook path via PostgREST RPC with the service role. It is
-- SECURITY INVOKER (runs with the caller's privileges), NOT definer: the write
-- to public.subscriptions therefore succeeds only for a role that actually
-- holds insert/update on that table (service_role). A DEFINER function here
-- would be an entitlement-forgery hole — PostgREST exposes public-schema RPCs
-- and Postgres grants EXECUTE to PUBLIC by default, so as definer any anon
-- caller could forge a paid plan for an arbitrary p_user_id. As invoker, anon/
-- authenticated (which lack the table grant) get permission denied; the
-- explicit REVOKE below removes even EXECUTE from PUBLIC for defense in depth.
create or replace function public.apply_subscription_event(
  p_user_id                uuid,
  p_plan_id                text,
  p_status                 text,
  p_stripe_customer_id     text,
  p_stripe_subscription_id text,
  p_current_period_end     timestamptz,
  p_cancel_at_period_end   boolean,
  p_event_created_at       bigint
)
returns void
language sql
security invoker
as $$
  insert into public.subscriptions as s (
    user_id, plan_id, status, stripe_customer_id, stripe_subscription_id,
    current_period_end, cancel_at_period_end, last_event_created_at
  )
  values (
    p_user_id, p_plan_id, p_status, p_stripe_customer_id, p_stripe_subscription_id,
    p_current_period_end, p_cancel_at_period_end, p_event_created_at
  )
  on conflict (user_id) do update set
    plan_id                = excluded.plan_id,
    status                 = excluded.status,
    stripe_customer_id     = excluded.stripe_customer_id,
    stripe_subscription_id = excluded.stripe_subscription_id,
    current_period_end     = excluded.current_period_end,
    cancel_at_period_end   = excluded.cancel_at_period_end,
    last_event_created_at  = excluded.last_event_created_at
  where s.last_event_created_at is null              -- row has no applied event yet
     or excluded.last_event_created_at is null       -- incoming event is unordered
     or excluded.last_event_created_at >= s.last_event_created_at;  -- same-or-newer wins
$$;

-- Processed Stripe events (webhook idempotency) -------------------------------
create table if not exists public.stripe_events (
  id           text primary key,   -- Stripe event id (evt_...)
  type         text not null,
  processed_at timestamptz not null default now()
);

comment on table public.stripe_events is
  'Log of processed Stripe webhook event IDs for idempotency. Service role only.';

-- Row Level Security ----------------------------------------------------------
alter table public.plans         enable row level security;
alter table public.subscriptions enable row level security;
alter table public.stripe_events enable row level security;

-- plans: any authenticated user can read the public catalog; no client writes.
create policy "plans_read_authenticated"
  on public.plans for select
  to authenticated
  using (true);

-- subscriptions: a user reads only their own row; admins read all. All writes go
-- through the service role (webhook), which bypasses RLS — so no client
-- INSERT/UPDATE/DELETE policies are granted.
create policy "subscriptions_select_own"
  on public.subscriptions for select
  to authenticated
  using (user_id = auth.uid());

create policy "subscriptions_select_admin"
  on public.subscriptions for select
  to authenticated
  using (public.is_admin());

-- stripe_events: no client access at all (service role bypasses RLS).

-- Grants ----------------------------------------------------------------------
grant select on public.plans to anon, authenticated, service_role;
grant select on public.subscriptions to authenticated, service_role;
grant insert, update on public.subscriptions to service_role;
grant select, insert on public.stripe_events to service_role;
-- The webhook applies subscription events through this function (out-of-order
-- guard); the service role calls it via PostgREST RPC.
grant execute on function public.apply_subscription_event(
  uuid, text, text, text, text, timestamptz, boolean, bigint
) to service_role;
-- Remove the PUBLIC default EXECUTE grant so only service_role can call the
-- RPC (defense in depth; SECURITY INVOKER already blocks the table write for
-- anon/authenticated, but this keeps the RPC off the anon-reachable surface).
revoke execute on function public.apply_subscription_event(
  uuid, text, text, text, text, timestamptz, boolean, bigint
) from public;

-- =============================================================================
-- GENERATION — jobs, generated files, provider runs, usage meter
-- =============================================================================
-- The AI media-generation slice. All rows are written ONLY by the server via the
-- service role (the generation service already holds the validated user id); the
-- browser never writes here. Reads are RLS-scoped to the owner (admins see all).
-- The B2 bucket remains the source of truth for the bytes; `public.files` mirrors
-- the object key + provenance so a user's generations are queryable without a
-- bucket scan per request.

-- Generation jobs (one text-to-image run) -------------------------------------
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

-- Generated files (mirror of the B2 objects a job produced) -------------------
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

-- Provider runs (one row per external provider invocation — provenance) -------
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

-- Usage events (metering — one row per billable unit) -------------------------
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

-- Row Level Security ----------------------------------------------------------
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

-- Grants ----------------------------------------------------------------------
grant select on public.generation_jobs to authenticated, service_role;
grant insert, update on public.generation_jobs to service_role;

grant select on public.files to authenticated, service_role;
grant insert, update, delete on public.files to service_role;

grant select on public.provider_runs to authenticated, service_role;
grant insert on public.provider_runs to service_role;

grant select on public.usage_events to authenticated, service_role;
grant insert on public.usage_events to service_role;

-- =============================================================================
-- ADMIN — append-only audit log of state-changing admin actions
-- =============================================================================
create table if not exists public.admin_audit_events (
  id          uuid primary key default gen_random_uuid(),
  actor_id    uuid references auth.users (id) on delete set null,
  actor_email text,
  action      text not null,                       -- e.g. 'update_user_role'
  resource    text not null,                       -- e.g. 'user'
  target_id   text,                                -- id of the affected resource
  detail      jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);

create index if not exists admin_audit_events_created_idx
  on public.admin_audit_events (created_at desc);

comment on table public.admin_audit_events is
  'Append-only log of state-changing admin actions (who did what to which resource). Written server-side (service role) only; readable by admins via RLS.';

-- Row Level Security ----------------------------------------------------------
alter table public.admin_audit_events enable row level security;

-- Only admins may read the audit log; writes are service-role only (bypass RLS),
-- so there is no client INSERT/UPDATE/DELETE policy.
create policy "admin_audit_events_select_admin"
  on public.admin_audit_events for select to authenticated
  using (public.is_admin());

-- Grants ----------------------------------------------------------------------
grant select on public.admin_audit_events to authenticated, service_role;
grant insert on public.admin_audit_events to service_role;
