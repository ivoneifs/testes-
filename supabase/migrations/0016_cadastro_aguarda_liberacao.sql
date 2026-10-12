-- NeuroScore — quem libera o acesso é o administrador.
-- Cadastro novo entra com status 'pending' (aguardando liberação). Continua ganhando os 3 créditos
-- de boas-vindas, mas só usa depois que o admin muda o status para 'active' (e escolhe Teste/Pro).
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, full_name, email, trial_ends_at, credits, status)
  values (new.id, new.raw_user_meta_data->>'full_name', new.email, now() + interval '14 days', 3, 'pending')
  on conflict (id) do update set email = excluded.email;
  if found then
    insert into public.credit_ledger(owner, delta, reason, ref, balance_after)
    select new.id, 3, 'trial_bonus', 'teste 14 dias', 3
    where not exists (select 1 from public.credit_ledger where owner = new.id and reason = 'trial_bonus');
  end if;
  return new;
end $$;

-- inserção pelo próprio usuário (sem o trigger acima) também começa aguardando liberação
create or replace function public.protect_profile_fields()
returns trigger language plpgsql set search_path = public as $$
begin
  if current_user not in ('authenticated', 'anon') or public.is_admin() then
    return new;
  end if;

  if tg_op = 'INSERT' then
    new.role          := 'professional';
    new.status        := 'pending';
    new.plan          := null;
    new.credits       := 0;
    new.trial_ends_at := now() + interval '14 days';
  elsif new.role          is distinct from old.role
     or new.status        is distinct from old.status
     or new.plan          is distinct from old.plan
     or new.credits       is distinct from old.credits
     or new.trial_ends_at is distinct from old.trial_ends_at then
    raise exception 'Somente o administrador pode alterar papel, status, plano, créditos ou período de teste.'
      using errcode = '42501';
  end if;
  return new;
end $$;
