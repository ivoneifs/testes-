-- NeuroScore — créditos por uso (aceita meio crédito).
--   História de Vida (análise da anamnese) = 0,5 · cada teste corrigido = 1 · laudo = 1
-- Saldo zerado → os serviços pagos respondem 402 até o usuário comprar créditos.

alter table public.profiles      alter column credits       type numeric(12,2) using credits::numeric;
alter table public.credit_ledger alter column delta         type numeric(12,2) using delta::numeric;
alter table public.credit_ledger alter column balance_after type numeric(12,2) using balance_after::numeric;

drop function if exists public.apply_credits(uuid, integer, text, text);
create or replace function public.apply_credits(p_owner uuid, p_delta numeric, p_reason text, p_ref text default null)
returns numeric language plpgsql security definer set search_path = public as $$
declare new_balance numeric;
begin
  update public.profiles set credits = greatest(credits + p_delta, 0)
    where id = p_owner returning credits into new_balance;
  if new_balance is null then raise exception 'profile_not_found'; end if;
  insert into public.credit_ledger(owner, delta, reason, ref, balance_after)
    values (p_owner, p_delta, p_reason, p_ref, new_balance);
  return new_balance;
end $$;

-- Débito genérico. Admin é ilimitado. Com p_ref, repetir o mesmo serviço
-- (mesmo motivo + mesma referência) no mesmo dia não cobra de novo — ex.:
-- recalcular o mesmo teste do mesmo paciente depois de corrigir um escore.
create or replace function public.spend_credits(p_amount numeric, p_reason text, p_ref text default null)
returns numeric language plpgsql security definer set search_path = public as $$
declare uid uuid := auth.uid(); bal numeric;
begin
  if (select role from public.profiles where id = uid) = 'admin' then
    return 999999;
  end if;
  select credits into bal from public.profiles where id = uid for update;
  if p_ref is not null and exists (
    select 1 from public.credit_ledger
     where owner = uid and reason = p_reason and ref = p_ref
       and created_at >= date_trunc('day', now())) then
    return bal;
  end if;
  if coalesce(bal, 0) < p_amount then
    raise exception 'insufficient_credits';
  end if;
  return public.apply_credits(uid, -p_amount, p_reason, p_ref);
end $$;

-- Laudo: sempre cobra 1 (sem a regra do "mesmo dia"); p_ref só vai para o extrato.
drop function if exists public.spend_laudo(text);
create or replace function public.spend_laudo(p_ref text default null)
returns numeric language plpgsql security definer set search_path = public as $$
declare uid uuid := auth.uid(); bal numeric;
begin
  if (select role from public.profiles where id = uid) = 'admin' then
    return 999999;
  end if;
  select credits into bal from public.profiles where id = uid for update;
  if coalesce(bal, 0) < 1 then
    raise exception 'insufficient_credits';
  end if;
  return public.apply_credits(uid, -1, 'laudo', p_ref);
end $$;
grant execute on function public.spend_laudo(text) to authenticated;

grant execute on function public.spend_credits(numeric, text, text) to authenticated;

-- Textos dos pacotes: 1 crédito = 1 teste ou laudo; História de Vida = 0,5
update public.plans set features = '["10 créditos (1 teste ou laudo cada)","História de Vida por 0,5 crédito","Exportação em Word e PDF","Suporte por e-mail"]'::jsonb where key = 'inicial';
update public.plans set features = '["20 créditos (1 teste ou laudo cada)","História de Vida por 0,5 crédito","Exportação em Word e PDF","Suporte prioritário via WhatsApp"]'::jsonb where key = 'profissional';
update public.plans set features = '["30 créditos (1 teste ou laudo cada)","História de Vida por 0,5 crédito","Exportação em Word e PDF","Suporte prioritário + onboarding"]'::jsonb where key = 'premium';
