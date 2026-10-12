-- NeuroScore — conta de teste (cadastro novo) começa com 3 créditos grátis, registrados no extrato.

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, full_name, email, trial_ends_at, credits)
  values (new.id, new.raw_user_meta_data->>'full_name', new.email, now() + interval '14 days', 3)
  on conflict (id) do update set email = excluded.email;
  if found then
    insert into public.credit_ledger(owner, delta, reason, ref, balance_after)
    select new.id, 3, 'trial_bonus', 'teste 14 dias', 3
    where not exists (select 1 from public.credit_ledger where owner = new.id and reason = 'trial_bonus');
  end if;
  return new;
end $$;
