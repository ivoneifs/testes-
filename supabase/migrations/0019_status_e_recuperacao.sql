-- 0019 — Status do sistema (painel Admin) e recuperação de senha por WhatsApp
-- system_status: escrito pelo servidor (backup diário, monitor de disponibilidade); só o admin lê.
create table if not exists public.system_status (
  key text primary key,
  value jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.system_status enable row level security;
drop policy if exists system_status_admin_read on public.system_status;
create policy system_status_admin_read on public.system_status for select using (public.is_admin());
revoke insert, update, delete, truncate on public.system_status from anon, authenticated;

-- códigos de recuperação de senha (só o servidor, via service_role, lê e escreve)
create table if not exists public.password_resets (
  id bigserial primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  code_hash text not null,
  expires_at timestamptz not null,
  attempts int not null default 0,
  used_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists password_resets_user_idx on public.password_resets(user_id, created_at desc);
alter table public.password_resets enable row level security;
revoke all on public.password_resets from anon, authenticated;
revoke all on sequence public.password_resets_id_seq from anon, authenticated;
