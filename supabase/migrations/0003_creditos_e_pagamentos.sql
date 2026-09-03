-- NeuroScore — créditos de laudo, histórico e pedidos de pagamento
-- Aplicar: Supabase Dashboard -> SQL Editor.

-- ---------------- razão dos créditos (extrato) ----------------
create table if not exists public.credit_ledger (
  id            bigint generated always as identity primary key,
  owner         uuid not null references auth.users(id) on delete cascade,
  delta         integer not null,            -- +N compra / -1 laudo / +N ajuste admin
  reason        text not null,               -- purchase | laudo | admin_grant | refund
  ref           text,                        -- id do pagamento / da avaliação
  balance_after integer,
  created_at    timestamptz not null default now()
);
create index if not exists credit_ledger_owner_idx on public.credit_ledger(owner, created_at desc);
alter table public.credit_ledger enable row level security;
drop policy if exists "credit_ledger_read" on public.credit_ledger;
create policy "credit_ledger_read" on public.credit_ledger for select
  using (owner = auth.uid() or public.is_admin());
-- inserts só pelo backend (service role, ignora RLS)

-- ---------------- pedidos de compra ----------------
create table if not exists public.orders (
  id           uuid primary key default gen_random_uuid(),
  owner        uuid not null references auth.users(id) on delete cascade,
  pack         text not null,                -- inicial | profissional | premium
  credits      integer not null,
  amount_cents integer not null,
  provider     text not null default 'mercadopago',
  provider_ref text,                         -- preference id / external ref
  status       text not null default 'pending',  -- pending | paid | failed | cancelled
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index if not exists orders_owner_idx on public.orders(owner, created_at desc);
alter table public.orders enable row level security;
drop policy if exists "orders_read" on public.orders;
create policy "orders_read" on public.orders for select
  using (owner = auth.uid() or public.is_admin());
drop trigger if exists t_orders_touch on public.orders;
create trigger t_orders_touch before update on public.orders
  for each row execute function public.touch_updated_at();

-- ---------------- aplicação atômica de créditos ----------------
create or replace function public.apply_credits(p_owner uuid, p_delta int, p_reason text, p_ref text default null)
returns integer language plpgsql security definer set search_path = public as $$
declare new_balance int;
begin
  update public.profiles set credits = greatest(credits + p_delta, 0)
    where id = p_owner returning credits into new_balance;
  if new_balance is null then raise exception 'profile_not_found'; end if;
  insert into public.credit_ledger(owner, delta, reason, ref, balance_after)
    values (p_owner, p_delta, p_reason, p_ref, new_balance);
  return new_balance;
end $$;

-- consumo de 1 laudo (falha se não houver saldo e não for admin)
create or replace function public.spend_laudo(p_ref text default null)
returns integer language plpgsql security definer set search_path = public as $$
declare uid uuid := auth.uid(); bal int;
begin
  if (select role from public.profiles where id = uid) = 'admin' then
    return 999999;
  end if;
  select credits into bal from public.profiles where id = uid;
  if coalesce(bal,0) <= 0 then
    raise exception 'insufficient_credits';
  end if;
  return public.apply_credits(uid, -1, 'laudo', p_ref);
end $$;
