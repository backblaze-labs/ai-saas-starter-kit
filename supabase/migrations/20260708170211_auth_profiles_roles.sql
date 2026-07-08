-- Auth foundation for the SaaS starter: a roles catalog, a profiles table that
-- mirrors auth.users 1:1, RLS so users see only their own row (admins see all),
-- and triggers that (a) auto-create a profile on signup, (b) keep updated_at
-- fresh, and (c) prevent non-admins from escalating their own role.
--
-- Convenience for local/demo use: the FIRST user to sign up becomes an admin, so
-- the admin surface (built in a later slice) is exercisable out of the box.
-- SECURITY: on a PUBLIC hosted deploy this means the first stranger to register
-- gets admin. Before exposing a hosted instance, either sign up yourself first,
-- or remove the auto-promote branch in handle_new_user() below and grant admin
-- manually (e.g. `update public.profiles set role='admin' where email='you@…'`).

-- ---------------------------------------------------------------------------
-- Roles catalog
-- ---------------------------------------------------------------------------
create table if not exists public.roles (
  name        text primary key,
  description text
);

insert into public.roles (name, description) values
  ('user',  'Standard authenticated user'),
  ('admin', 'Administrator with full access to every resource')
on conflict (name) do nothing;

-- ---------------------------------------------------------------------------
-- Profiles (1:1 with auth.users)
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

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

-- Auto-create a profile row when a new auth user is inserted.
-- The first user ever created is promoted to admin (demo convenience).
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  assigned_role text := 'user';
begin
  if not exists (select 1 from public.profiles where role = 'admin') then
    assigned_role := 'admin';
  end if;

  insert into public.profiles (id, email, full_name, avatar_url, role)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'name'),
    new.raw_user_meta_data ->> 'avatar_url',
    assigned_role
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

-- ---------------------------------------------------------------------------
-- Triggers
-- ---------------------------------------------------------------------------
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

create trigger profiles_prevent_role_escalation
  before update on public.profiles
  for each row execute function public.prevent_role_escalation();

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
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
