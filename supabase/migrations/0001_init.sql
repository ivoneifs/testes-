-- NeuroScore — esquema inicial (Supabase Postgres)
-- Aplicar: Supabase Dashboard -> SQL Editor -> colar e rodar.
-- (ou: supabase link --project-ref <ref> && supabase db push)

-- ---------------- profiles (1:1 com auth.users) ----------------
create table if not exists public.profiles (
  id              uuid primary key references auth.users(id) on delete cascade,
  full_name       text,
  professional_id text,            -- registro profissional (CRP etc.)
  header          text,            -- cabeçalho padrão do laudo
  default_model   jsonb,           -- modelo de formatação padrão
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

-- ---------------- evaluations (uma avaliação de paciente) ----------------
create table if not exists public.evaluations (
  id                uuid primary key default gen_random_uuid(),
  owner             uuid not null default auth.uid() references auth.users(id) on delete cascade,
  patient           jsonb not null default '{}'::jsonb,
  tests             jsonb not null default '[]'::jsonb,   -- resultados calculados
  anamnesis         jsonb,
  test_reports      jsonb not null default '[]'::jsonb,
  integrated_report jsonb,
  laudo_model       jsonb,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);
create index if not exists evaluations_owner_idx on public.evaluations(owner, updated_at desc);

-- ---------------- audit_log ----------------
create table if not exists public.audit_log (
  id        bigint generated always as identity primary key,
  owner     uuid not null default auth.uid(),
  action    text not null,
  entity    text,
  entity_id uuid,
  meta      jsonb not null default '{}'::jsonb,
  at        timestamptz not null default now()
);
create index if not exists audit_owner_idx on public.audit_log(owner, at desc);

-- ---------------- RLS ----------------
alter table public.profiles    enable row level security;
alter table public.evaluations enable row level security;
alter table public.audit_log   enable row level security;

drop policy if exists "profiles_own" on public.profiles;
create policy "profiles_own" on public.profiles
  for all using (id = auth.uid()) with check (id = auth.uid());

drop policy if exists "evaluations_own" on public.evaluations;
create policy "evaluations_own" on public.evaluations
  for all using (owner = auth.uid()) with check (owner = auth.uid());

drop policy if exists "audit_select_own" on public.audit_log;
create policy "audit_select_own" on public.audit_log
  for select using (owner = auth.uid());

drop policy if exists "audit_insert_own" on public.audit_log;
create policy "audit_insert_own" on public.audit_log
  for insert with check (owner = auth.uid());

-- ---------------- triggers ----------------
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists t_profiles_touch on public.profiles;
create trigger t_profiles_touch before update on public.profiles
  for each row execute function public.touch_updated_at();

drop trigger if exists t_evaluations_touch on public.evaluations;
create trigger t_evaluations_touch before update on public.evaluations
  for each row execute function public.touch_updated_at();

-- cria um profile automaticamente quando um usuário se registra
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, full_name)
  values (new.id, new.raw_user_meta_data->>'full_name')
  on conflict (id) do nothing;
  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();
