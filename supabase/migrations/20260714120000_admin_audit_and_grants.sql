-- Admin slice (B4): the admin audit log, plus the portable table GRANTs the
-- first (auth) migration was missing for public.profiles / public.roles.
--
-- WHY THE GRANTS (and why here, not a db reset): RLS decides which ROWS a role
-- sees; table-level GRANTs decide whether a role may touch the table at all.
-- Tables created by `postgres` in a migration do not portably inherit DML grants
-- for the API roles (anon / authenticated / service_role) on every instance. The
-- billing and generation migrations already grant explicitly, but the auth
-- migration did not — so a client read of public.profiles 403s at the grant layer
-- (before RLS), and both the backend `fetch_profile_role` and the browser's
-- useAuth() silently fall back to role = 'user'. That would make the admin
-- surface unreachable for a real admin. Granting here is forward-only and
-- idempotent, so it fixes existing local databases without a destructive reset.

-- ---------------------------------------------------------------------------
-- Backfill the grants the auth migration missed (profiles + roles)
-- ---------------------------------------------------------------------------
grant select on public.roles to anon, authenticated, service_role;

grant select on public.profiles to authenticated, service_role;
-- own-row + admin profile updates are gated by the RLS policies from the auth
-- migration; the table-level UPDATE grant is what makes those policies reachable.
grant update on public.profiles to authenticated;
grant insert, update, delete on public.profiles to service_role;

-- ---------------------------------------------------------------------------
-- Admin audit log (append-only; one row per state-changing admin action)
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
alter table public.admin_audit_events enable row level security;

-- Only admins may read the audit log; writes are service-role only (bypass RLS),
-- so there is no client INSERT/UPDATE/DELETE policy.
create policy "admin_audit_events_select_admin"
  on public.admin_audit_events for select to authenticated
  using (public.is_admin());

-- ---------------------------------------------------------------------------
-- Table grants
-- ---------------------------------------------------------------------------
grant select on public.admin_audit_events to authenticated, service_role;
grant insert on public.admin_audit_events to service_role;
