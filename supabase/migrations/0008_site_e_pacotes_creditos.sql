-- NeuroScore — configurações do site (cores + textos da landing) editáveis pelo admin
-- e pacotes de créditos a R$ 20/crédito (10, 20, 30).

create table if not exists public.site_settings (
  id         text primary key default 'site',
  data       jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.site_settings enable row level security;
drop policy if exists "site_read"  on public.site_settings;
drop policy if exists "site_write" on public.site_settings;
create policy "site_read"  on public.site_settings for select using (true);
create policy "site_write" on public.site_settings for all
  using (public.is_admin()) with check (public.is_admin());
drop trigger if exists t_site_touch on public.site_settings;
create trigger t_site_touch before update on public.site_settings
  for each row execute function public.touch_updated_at();
grant select on public.site_settings to anon, authenticated;
grant insert, update, delete on public.site_settings to authenticated;

insert into public.site_settings (id, data) values ('site', '{}'::jsonb)
on conflict (id) do nothing;

-- Pacotes: cada crédito = R$ 20,00
update public.plans set name = 'Pack 10 créditos', credits = 10, amount_cents = 20000, featured = false, active = true, sort = 1,
  features = '["10 laudos completos com IA","Correção automática de 70+ instrumentos","Exportação em Word e PDF","Suporte por e-mail"]'::jsonb
  where key = 'inicial';
update public.plans set name = 'Pack 20 créditos', credits = 20, amount_cents = 40000, featured = true, active = true, sort = 2,
  features = '["20 laudos completos com IA","Correção automática de 70+ instrumentos","Exportação em Word e PDF","Suporte prioritário via WhatsApp"]'::jsonb
  where key = 'profissional';
update public.plans set name = 'Pack 30 créditos', credits = 30, amount_cents = 60000, featured = false, active = true, sort = 3,
  features = '["30 laudos completos com IA","Correção automática de 70+ instrumentos","Exportação em Word e PDF","Suporte prioritário + onboarding"]'::jsonb
  where key = 'premium';
