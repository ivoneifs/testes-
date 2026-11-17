-- 0018 — Auditoria de segurança (2026-11-17)
-- 1) apply_credits é SECURITY DEFINER e estava executável por anon/authenticated
--    via PostgREST (/rest/v1/rpc/apply_credits): qualquer um podia se dar créditos.
--    Só o servidor (service_role) e as funções internas (spend_*) a chamam.
-- 2) spend_credits aceitava valor negativo (gastar -N = ganhar N).
-- 3) Funções internas/gatilho sem motivo para ficarem expostas na API.

revoke execute on function public.apply_credits(uuid, numeric, text, text) from public, anon, authenticated;
grant  execute on function public.apply_credits(uuid, numeric, text, text) to service_role;

revoke execute on function public.handle_new_user() from public, anon, authenticated;
revoke execute on function public.spend_credits(numeric, text, text) from public, anon;
revoke execute on function public.spend_laudo(text) from public, anon;
revoke execute on function public.dashboard_summary() from public, anon;

create or replace function public.spend_credits(p_amount numeric, p_reason text, p_ref text default null)
returns numeric language plpgsql security definer set search_path = public as $$
declare uid uuid := auth.uid(); bal numeric;
begin
  if uid is null then raise exception 'not_authenticated' using errcode = '42501'; end if;
  if p_amount is null or p_amount <= 0 then raise exception 'invalid_amount' using errcode = '22023'; end if;
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

create or replace function public.spend_laudo(p_ref text default null)
returns numeric language plpgsql security definer set search_path = public as $$
declare uid uuid := auth.uid(); bal numeric;
begin
  if uid is null then raise exception 'not_authenticated' using errcode = '42501'; end if;
  if (select role from public.profiles where id = uid) = 'admin' then
    return 999999;
  end if;
  select credits into bal from public.profiles where id = uid for update;
  if coalesce(bal, 0) < 1 then
    raise exception 'insufficient_credits';
  end if;
  return public.apply_credits(uid, -1, 'laudo', p_ref);
end $$;

-- pedidos: o usuário só cria pedido 'pending' (quem marca 'paid' é o webhook com service_role)
drop policy if exists orders_insert on public.orders;
create policy orders_insert on public.orders for insert
  with check (owner = auth.uid() and coalesce(status, 'pending') = 'pending');
