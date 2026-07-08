-- Billing foundation for the SaaS starter: a plan catalog (Free/Pro/Team), one
-- synced subscription row per user (written ONLY by the Stripe webhook via the
-- service role — never by the browser), and a processed-events log for webhook
-- idempotency.
--
-- Stripe price IDs are account-specific, so they live in env config
-- (STRIPE_PRICE_PRO / STRIPE_PRICE_TEAM) and are resolved by the backend — they
-- are deliberately NOT stored here, so this catalog is portable across any
-- Stripe account. The `plans` table is display + entitlement metadata only.
--
-- Reuses public.set_updated_at() and public.is_admin() from the auth migration.

-- ---------------------------------------------------------------------------
-- Plan catalog (display + entitlement metadata)
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- Subscriptions (one synced row per user; source of truth is Stripe)
-- ---------------------------------------------------------------------------
create table if not exists public.subscriptions (
  user_id                uuid primary key references auth.users (id) on delete cascade,
  plan_id                text not null default 'free' references public.plans (id),
  status                 text not null default 'inactive',  -- active|trialing|past_due|canceled|incomplete|inactive
  stripe_customer_id     text,
  stripe_subscription_id text,
  current_period_end     timestamptz,
  cancel_at_period_end   boolean not null default false,
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

-- ---------------------------------------------------------------------------
-- Processed Stripe events (webhook idempotency)
-- ---------------------------------------------------------------------------
create table if not exists public.stripe_events (
  id           text primary key,   -- Stripe event id (evt_...)
  type         text not null,
  processed_at timestamptz not null default now()
);

comment on table public.stripe_events is
  'Log of processed Stripe webhook event IDs for idempotency. Service role only.';

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- Table grants
-- ---------------------------------------------------------------------------
-- RLS decides which ROWS a role sees; table-level GRANTs decide whether a role
-- may touch the table at all. A well-configured Supabase project grants these to
-- the API roles by default, but tables created by `postgres` in a migration only
-- inherit TRUNCATE/REFERENCES/TRIGGER on some instances — so grant explicitly to
-- keep this migration portable. The billing backend reaches these tables with the
-- service role; the SELECT grants to authenticated/anon make the RLS read
-- policies above reachable for any direct client reads.
grant select on public.plans to anon, authenticated, service_role;
grant select on public.subscriptions to authenticated, service_role;
grant insert, update on public.subscriptions to service_role;
grant select, insert on public.stripe_events to service_role;
