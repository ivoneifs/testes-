-- NeuroScore — acesso de teste (trial). O administrador define o tipo de acesso:
--   Admin  → role = 'admin'
--   Pro    → role = 'professional', trial_ends_at = null
--   Teste  → role = 'professional', trial_ends_at = data em que o acesso expira
-- Contas criadas pela tela de cadastro começam em teste de 14 dias.
-- Expirado, o app bloqueia tudo (exceto ver o perfil e comprar créditos).

alter table public.profiles add column if not exists trial_ends_at timestamptz;

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, full_name, email, trial_ends_at)
  values (new.id, new.raw_user_meta_data->>'full_name', new.email, now() + interval '14 days')
  on conflict (id) do update set email = excluded.email;
  return new;
end $$;

-- O próprio usuário não pode estender o teste.
create or replace function public.protect_profile_fields()
returns trigger language plpgsql set search_path = public as $$
begin
  if current_user not in ('authenticated', 'anon') or public.is_admin() then
    return new;
  end if;

  if tg_op = 'INSERT' then
    new.role          := 'professional';
    new.status        := 'active';
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
