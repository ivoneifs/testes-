-- NeuroScore — cadastro com os dados do profissional (CRP, WhatsApp, cidade) para o admin
-- conferir antes de aprovar; status 'rejected' = cadastro recusado pelo admin.
alter table public.profiles add column if not exists phone text;
alter table public.profiles add column if not exists city  text;

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, full_name, email, professional_id, phone, city, trial_ends_at, credits, status)
  values (new.id, new.raw_user_meta_data->>'full_name', new.email,
          nullif(new.raw_user_meta_data->>'professional_id', ''),
          nullif(new.raw_user_meta_data->>'phone', ''),
          nullif(new.raw_user_meta_data->>'city', ''),
          now() + interval '14 days', 3, 'pending')
  on conflict (id) do update set email = excluded.email;
  if found then
    insert into public.credit_ledger(owner, delta, reason, ref, balance_after)
    select new.id, 3, 'trial_bonus', 'teste 14 dias', 3
    where not exists (select 1 from public.credit_ledger where owner = new.id and reason = 'trial_bonus');
  end if;
  return new;
end $$;
