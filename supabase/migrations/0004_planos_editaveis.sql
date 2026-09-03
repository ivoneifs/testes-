-- NeuroScore — planos/pacotes editáveis pelo administrador

create table if not exists public.plans (
  key          text primary key,
  name         text not null,
  credits      integer not null,
  amount_cents integer not null,
  features     jsonb   not null default '[]'::jsonb,
  featured     boolean not null default false,
  active       boolean not null default true,
  sort         integer not null default 0,
  updated_at   timestamptz not null default now()
);
alter table public.plans enable row level security;
drop policy if exists "plans_read"  on public.plans;
drop policy if exists "plans_write" on public.plans;
create policy "plans_read"  on public.plans for select using (true);
create policy "plans_write" on public.plans for all
  using (public.is_admin()) with check (public.is_admin());
drop trigger if exists t_plans_touch on public.plans;
create trigger t_plans_touch before update on public.plans
  for each row execute function public.touch_updated_at();

insert into public.plans (key, name, credits, amount_cents, features, featured, sort) values
  ('inicial',      'Pack Inicial',         5,  4900,  '["Suporte via e-mail","Exportação em PDF","IA para laudos"]'::jsonb,                      false, 1),
  ('profissional', 'Pack Profissional',    20, 14900, '["Prioridade na fila","Suporte WhatsApp","História de Vida ilimitada"]'::jsonb,          true,  2),
  ('premium',      'Pack Clínica Premium', 50, 29900, '["Consultoria VIP","Treinamento de equipe","Personalização de layout"]'::jsonb,          false, 3)
on conflict (key) do nothing;
