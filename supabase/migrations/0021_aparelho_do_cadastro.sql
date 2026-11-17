-- NeuroScore — identificação do aparelho de quem pede a liberação (o MAC não chega pela web).
-- device_id: código aleatório gravado no navegador · device_fp: impressão digital do aparelho.
alter table public.profiles add column if not exists signup_device_id text;
alter table public.profiles add column if not exists signup_device_fp text;
alter table public.profiles add column if not exists last_device_id   text;
alter table public.profiles add column if not exists last_device_fp   text;

create or replace function public.protect_profile_fields()
returns trigger language plpgsql set search_path = public as $$
begin
  if current_user not in ('authenticated', 'anon') or public.is_admin() then
    return new;
  end if;

  if tg_op = 'INSERT' then
    new.role              := 'professional';
    new.status            := 'pending';
    new.plan              := null;
    new.credits           := 0;
    new.trial_ends_at     := now() + interval '14 days';
    new.signup_ip         := null;
    new.signup_ip_at      := null;
    new.signup_user_agent := null;
    new.last_ip           := null;
    new.last_ip_at        := null;
    new.signup_device_id  := null;
    new.signup_device_fp  := null;
    new.last_device_id    := null;
    new.last_device_fp    := null;
  elsif new.role          is distinct from old.role
     or new.status        is distinct from old.status
     or new.plan          is distinct from old.plan
     or new.credits       is distinct from old.credits
     or new.trial_ends_at is distinct from old.trial_ends_at then
    raise exception 'Somente o administrador pode alterar papel, status, plano, créditos ou período de teste.'
      using errcode = '42501';
  else
    new.signup_ip         := old.signup_ip;
    new.signup_ip_at      := old.signup_ip_at;
    new.signup_user_agent := old.signup_user_agent;
    new.last_ip           := old.last_ip;
    new.last_ip_at        := old.last_ip_at;
    new.signup_device_id  := old.signup_device_id;
    new.signup_device_fp  := old.signup_device_fp;
    new.last_device_id    := old.last_device_id;
    new.last_device_fp    := old.last_device_fp;
  end if;
  return new;
end $$;
