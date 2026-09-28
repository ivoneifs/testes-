-- Impede que um profissional altere, via API REST direta, os campos que só o
-- administrador controla (role, status, plan, credits). Sem isso a policy
-- "profiles_update" deixava o usuário se promover a admin na própria linha.
--
-- Chamadas vindas do cliente rodam como `authenticated`/`anon`; funções
-- security definer (spend_laudo, apply_credits, handle_new_user) e a
-- service_role rodam com outro current_user e seguem liberadas.

create or replace function public.protect_profile_fields()
returns trigger language plpgsql set search_path = public as $$
begin
  if current_user not in ('authenticated', 'anon') or public.is_admin() then
    return new;
  end if;

  if tg_op = 'INSERT' then
    new.role    := 'professional';
    new.status  := 'active';
    new.plan    := null;
    new.credits := 0;
  elsif new.role    is distinct from old.role
     or new.status  is distinct from old.status
     or new.plan    is distinct from old.plan
     or new.credits is distinct from old.credits then
    raise exception 'Somente o administrador pode alterar papel, status, plano ou créditos.'
      using errcode = '42501';
  end if;
  return new;
end $$;

drop trigger if exists t_profiles_protect on public.profiles;
create trigger t_profiles_protect
  before insert or update on public.profiles
  for each row execute function public.protect_profile_fields();
