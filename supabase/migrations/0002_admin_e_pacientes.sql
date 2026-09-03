-- NeuroScore — perfis com papel/plano, área administrativa e pacientes
-- Aplicar: Supabase Dashboard -> SQL Editor -> colar e rodar.

-- ---------------- profiles: novas colunas ----------------
alter table public.profiles add column if not exists role       text    not null default 'professional';  -- professional | admin
alter table public.profiles add column if not exists status     text    not null default 'active';        -- active | suspended
alter table public.profiles add column if not exists avatar_url text;
alter table public.profiles add column if not exists prefs      jsonb   not null default '{}'::jsonb;      -- tema, notificações
alter table public.profiles add column if not exists plan       text;                                    -- inicial | profissional | premium
alter table public.profiles add column if not exists credits    integer not null default 0;               -- créditos de laudo
alter table public.profiles add column if not exists email      text;

-- Espelha o e-mail do auth no profile (facilita a listagem administrativa).
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, full_name, email)
  values (new.id, new.raw_user_meta_data->>'full_name', new.email)
  on conflict (id) do update set email = excluded.email;
  return new;
end $$;

update public.profiles p set email = u.email
  from auth.users u where u.id = p.id and p.email is distinct from u.email;

-- ---------------- helper: é admin? ----------------
create or replace function public.is_admin()
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.profiles where id = auth.uid() and role = 'admin');
$$;

-- ---------------- RLS: admin tem controle total ----------------
drop policy if exists "profiles_own"    on public.profiles;
drop policy if exists "profiles_select" on public.profiles;
drop policy if exists "profiles_update" on public.profiles;
drop policy if exists "profiles_insert" on public.profiles;
drop policy if exists "profiles_delete" on public.profiles;
create policy "profiles_select" on public.profiles for select
  using (id = auth.uid() or public.is_admin());
create policy "profiles_insert" on public.profiles for insert
  with check (id = auth.uid());
create policy "profiles_update" on public.profiles for update
  using (id = auth.uid() or public.is_admin())
  with check (id = auth.uid() or public.is_admin());
create policy "profiles_delete" on public.profiles for delete
  using (public.is_admin());

drop policy if exists "evaluations_own" on public.evaluations;
create policy "evaluations_rw" on public.evaluations for all
  using (owner = auth.uid() or public.is_admin())
  with check (owner = auth.uid() or public.is_admin());

-- ---------------- pacientes (CRUD por profissional) ----------------
create table if not exists public.patients (
  id          uuid primary key default gen_random_uuid(),
  owner       uuid not null default auth.uid() references auth.users(id) on delete cascade,
  name        text not null,
  birth_date  date,
  sex         text,
  education   text,
  notes       text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists patients_owner_idx on public.patients(owner, updated_at desc);
alter table public.patients enable row level security;
drop policy if exists "patients_rw" on public.patients;
create policy "patients_rw" on public.patients for all
  using (owner = auth.uid() or public.is_admin())
  with check (owner = auth.uid() or public.is_admin());
drop trigger if exists t_patients_touch on public.patients;
create trigger t_patients_touch before update on public.patients
  for each row execute function public.touch_updated_at();

-- ---------------- conta administradora mestre ----------------
update public.profiles
   set role = 'admin', status = 'active'
 where id in (select id from auth.users where lower(email) = 'ivoneifs@gmail.com');
