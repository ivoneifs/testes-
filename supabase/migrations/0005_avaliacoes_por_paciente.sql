-- NeuroScore — vincula avaliações ao paciente cadastrado + resumo do dashboard

alter table public.evaluations add column if not exists patient_id uuid
  references public.patients(id) on delete set null;
create index if not exists evaluations_patient_idx on public.evaluations(patient_id);

create or replace function public.dashboard_summary()
returns jsonb language sql stable security definer set search_path = public as $$
  with mine_eval as (
    select * from public.evaluations
    where owner = auth.uid() or public.is_admin()
  )
  select jsonb_build_object(
    'evaluations', (select count(*) from mine_eval),
    'patients',    (select count(*) from public.patients
                    where owner = auth.uid() or public.is_admin()),
    'by_month', (
      select coalesce(jsonb_agg(jsonb_build_object('m', m, 'n', n) order by m), '[]'::jsonb)
      from (
        select to_char(date_trunc('month', created_at), 'YYYY-MM') m, count(*) n
        from mine_eval
        where created_at > now() - interval '12 months'
        group by 1
      ) s
    ),
    'top_tests', (
      select coalesce(jsonb_agg(jsonb_build_object('t', t, 'n', n) order by n desc), '[]'::jsonb)
      from (
        select el->>'test' t, count(*) n
        from mine_eval e,
             jsonb_array_elements(
               case when jsonb_typeof(e.tests) = 'array' then e.tests else '[]'::jsonb end
             ) el
        where el->>'test' is not null
        group by 1
        order by n desc
        limit 8
      ) s
    )
  );
$$;
