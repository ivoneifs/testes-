-- NeuroScore — "Testes realizados": cada teste corrigido fica salvo por paciente
-- (entradas + resultado do motor). Um registro por profissional + paciente + teste:
-- recalcular atualiza o mesmo registro. No fim, os selecionados viram o laudo completo.

create table if not exists public.test_results (
  id          uuid primary key default gen_random_uuid(),
  owner       uuid not null default auth.uid() references auth.users(id) on delete cascade,
  patient_id  uuid references public.patients(id) on delete set null,
  patient_key text not null,               -- nome normalizado + nascimento
  patient     jsonb not null default '{}'::jsonb,
  test        text not null,
  inputs      jsonb not null default '{}'::jsonb,   -- {raw_scores, parameters}
  result      jsonb not null default '{}'::jsonb,   -- resposta do motor (/api/score)
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (owner, patient_key, test)
);
create index if not exists test_results_owner_idx on public.test_results(owner, patient_key, updated_at desc);
alter table public.test_results enable row level security;
drop policy if exists "test_results_own" on public.test_results;
create policy "test_results_own" on public.test_results for all
  using (owner = auth.uid() or public.is_admin()) with check (owner = auth.uid() or public.is_admin());
drop trigger if exists t_test_results_touch on public.test_results;
create trigger t_test_results_touch before update on public.test_results
  for each row execute function public.touch_updated_at();
grant select, insert, update, delete on public.test_results to authenticated;
