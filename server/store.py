"""Persistência no Postgres do Supabase via PostgREST (sem driver de banco).

Todas as chamadas usam o JWT do usuário — as políticas RLS do Supabase
garantem que cada profissional só enxerga os próprios dados.
"""
from __future__ import annotations

import httpx
from fastapi import HTTPException

from .auth import AUTH_ENABLED, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

REST = f'{SUPABASE_URL}/rest/v1' if SUPABASE_URL else ''


def _headers(user: dict, *, write: bool = False) -> dict:
    token = user.get('token') or SUPABASE_ANON_KEY
    h = {
        'apikey': SUPABASE_ANON_KEY,
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
    }
    if write:
        h['Content-Type'] = 'application/json'
        h['Prefer'] = 'return=representation,resolution=merge-duplicates'
    return h


def _require() -> None:
    if not AUTH_ENABLED:
        raise HTTPException(400, 'Persistência indisponível: configure SUPABASE_URL e SUPABASE_ANON_KEY.')


async def _req(method: str, path: str, user: dict, *, params=None, json=None, write=False):
    _require()
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.request(method, f'{REST}{path}', headers=_headers(user, write=write),
                                 params=params, json=json)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f'Supabase: {r.text[:400]}')
    if r.status_code == 204 or not r.content:
        return None
    return r.json()


# ---------- avaliações ----------
async def list_evaluations(user: dict, patient_id: str | None = None) -> list[dict]:
    params = {
        'select': 'id,patient,patient_id,tests,integrated_report,created_at,updated_at',
        'order': 'updated_at.desc', 'limit': '200',
    }
    if patient_id:
        params['patient_id'] = f'eq.{patient_id}'
    return await _req('GET', '/evaluations', user, params=params) or []


async def get_evaluation(user: dict, eval_id: str) -> dict:
    rows = await _req('GET', '/evaluations', user, params={'id': f'eq.{eval_id}', 'limit': '1'}) or []
    if not rows:
        raise HTTPException(404, 'Avaliação não encontrada.')
    return rows[0]


async def save_evaluation(user: dict, payload: dict, eval_id: str | None = None) -> dict:
    body = {
        'patient': payload.get('patient') or {},
        'tests': payload.get('results') or payload.get('tests') or [],
        'anamnesis': payload.get('anamnesis'),
        'test_reports': payload.get('test_reports') or [],
        'integrated_report': payload.get('integrated_report'),
        'laudo_model': payload.get('laudo_model'),
    }
    if payload.get('patient_id'):
        body['patient_id'] = payload['patient_id']
    if eval_id:
        rows = await _req('PATCH', '/evaluations', user, params={'id': f'eq.{eval_id}'},
                          json=body, write=True)
    else:
        rows = await _req('POST', '/evaluations', user, json=body, write=True)
    row = (rows or [{}])[0]
    await log(user, 'save', 'evaluation', row.get('id'))
    return row


async def delete_evaluation(user: dict, eval_id: str) -> None:
    await _req('DELETE', '/evaluations', user, params={'id': f'eq.{eval_id}'})
    await log(user, 'delete', 'evaluation', eval_id)


# ---------- perfil ----------
async def get_profile(user: dict) -> dict:
    rows = await _req('GET', '/profiles', user, params={'id': f'eq.{user["id"]}', 'limit': '1'}) or []
    return rows[0] if rows else {'id': user['id']}


async def save_profile(user: dict, data: dict) -> dict:
    body = {'id': user['id']}
    for k in ('full_name', 'professional_id', 'header', 'default_model', 'avatar_url', 'prefs'):
        if k in data:
            body[k] = data[k]
    rows = await _req('POST', '/profiles', user, json=body, write=True)
    return (rows or [{}])[0]


async def is_admin(user: dict) -> bool:
    return (await get_profile(user)).get('role') == 'admin'


async def _require_admin(user: dict) -> None:
    if not await is_admin(user):
        raise HTTPException(403, 'Acesso restrito a administradores.')


# ---------- administração: profissionais ----------
_PRO_FIELDS = 'id,full_name,email,professional_id,role,status,plan,credits,created_at,updated_at'
_PRO_EDITABLE = ('full_name', 'professional_id', 'role', 'status', 'plan', 'credits')


async def list_professionals(user: dict) -> list[dict]:
    await _require_admin(user)
    return await _req('GET', '/profiles', user, params={
        'select': _PRO_FIELDS, 'order': 'created_at.desc', 'limit': '1000',
    }) or []


async def admin_update_professional(user: dict, pid: str, data: dict) -> dict:
    await _require_admin(user)
    body = {k: data[k] for k in _PRO_EDITABLE if data.get(k) is not None}
    if not body:
        raise HTTPException(400, 'Nada para atualizar.')
    rows = await _req('PATCH', '/profiles', user, params={'id': f'eq.{pid}'}, json=body, write=True)
    await log(user, 'admin_update', 'profile', pid, {'fields': list(body)})
    return (rows or [{}])[0]


async def admin_delete_professional(user: dict, pid: str) -> None:
    await _require_admin(user)
    if pid == user['id']:
        raise HTTPException(400, 'Não é possível excluir a própria conta.')
    # Remove o usuário de auth (o profile cai por cascade). Precisa do service role.
    if SUPABASE_SERVICE_ROLE_KEY:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.delete(
                f'{SUPABASE_URL}/auth/v1/admin/users/{pid}',
                headers={'apikey': SUPABASE_SERVICE_ROLE_KEY,
                         'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}'},
            )
        if r.status_code >= 400 and r.status_code != 404:
            raise HTTPException(r.status_code, f'Supabase: {r.text[:300]}')
    else:
        await _req('DELETE', '/profiles', user, params={'id': f'eq.{pid}'})
    await log(user, 'admin_delete', 'profile', pid)


# ---------- pacientes ----------
async def list_patients(user: dict) -> list[dict]:
    return await _req('GET', '/patients', user, params={
        'select': '*', 'order': 'updated_at.desc', 'limit': '1000',
    }) or []


async def save_patient(user: dict, data: dict, pid: str | None = None) -> dict:
    body = {k: data.get(k) for k in ('name', 'birth_date', 'sex', 'education', 'notes')}
    body = {k: v for k, v in body.items() if v is not None}
    if not body.get('name') and not pid:
        raise HTTPException(400, 'Nome do paciente é obrigatório.')
    if pid:
        rows = await _req('PATCH', '/patients', user, params={'id': f'eq.{pid}'}, json=body, write=True)
    else:
        rows = await _req('POST', '/patients', user, json=body, write=True)
    row = (rows or [{}])[0]
    await log(user, 'save', 'patient', row.get('id'))
    return row


async def delete_patient(user: dict, pid: str) -> None:
    await _req('DELETE', '/patients', user, params={'id': f'eq.{pid}'})
    await log(user, 'delete', 'patient', pid)


# ---------- auditoria ----------
async def log(user: dict, action: str, entity: str | None = None,
              entity_id=None, meta: dict | None = None) -> None:
    try:
        await _req('POST', '/audit_log', user, json={
            'action': action, 'entity': entity, 'entity_id': entity_id, 'meta': meta or {},
        }, write=True)
    except HTTPException:
        pass  # auditoria nunca deve quebrar a operação principal


async def list_audit(user: dict) -> list[dict]:
    return await _req('GET', '/audit_log', user, params={
        'select': 'action,entity,entity_id,meta,at', 'order': 'at.desc', 'limit': '200',
    }) or []


# ---------- créditos e pagamentos ----------
async def _service_req(method: str, path: str, *, params=None, json=None):
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(500, 'Service role não configurado no servidor.')
    h = {'apikey': SUPABASE_SERVICE_ROLE_KEY,
         'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
         'Content-Type': 'application/json', 'Prefer': 'return=representation'}
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.request(method, f'{REST}{path}', headers=h, params=params, json=json)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f'Supabase: {r.text[:300]}')
    return r.json() if r.content else None


def _scalar(v):
    return v[0] if isinstance(v, list) and v else v


async def credit_balance(user: dict) -> int:
    return int((await get_profile(user)).get('credits') or 0)


async def spend_laudo(user: dict, ref: str | None = None) -> int:
    """Consome 1 crédito (admin é ilimitado). 402 se não houver saldo."""
    try:
        return int(_scalar(await _req('POST', '/rpc/spend_laudo', user, json={'p_ref': ref}, write=True)) or 0)
    except HTTPException as e:
        if 'insufficient_credits' in str(e.detail):
            raise HTTPException(402, 'Créditos insuficientes. Compre um pacote em Planos para gerar o laudo.')
        raise


async def can_laudo(user: dict) -> bool:
    p = await get_profile(user)
    return p.get('role') == 'admin' or int(p.get('credits') or 0) > 0


async def list_ledger(user: dict) -> list[dict]:
    return await _req('GET', '/credit_ledger', user, params={
        'select': 'delta,reason,ref,balance_after,created_at', 'order': 'created_at.desc', 'limit': '100',
    }) or []


async def dashboard_summary(user: dict) -> dict:
    data = _scalar(await _req('POST', '/rpc/dashboard_summary', user, json={}, write=True))
    return data or {'evaluations': 0, 'patients': 0, 'by_month': [], 'top_tests': []}


async def list_plans(user: dict | None = None) -> list[dict]:
    # plans_read = using(true): qualquer sessão lê; anon key também serve.
    if user:
        return await _req('GET', '/plans', user, params={'select': '*', 'order': 'sort'}) or []
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get(f'{REST}/plans', params={'select': '*', 'order': 'sort'},
                        headers={'apikey': SUPABASE_ANON_KEY, 'Authorization': f'Bearer {SUPABASE_ANON_KEY}'})
    return r.json() if r.status_code < 400 and r.content else []


async def get_plan(user: dict | None, key: str) -> dict | None:
    for p in await list_plans(user):
        if p.get('key') == key and p.get('active'):
            return p
    return None


async def upsert_plan(user: dict, key: str, data: dict) -> dict:
    await _require_admin(user)
    body = {}
    for k in ('name', 'credits', 'amount_cents', 'features', 'featured', 'active', 'sort'):
        if data.get(k) is not None:
            body[k] = data[k]
    existing = await _req('GET', '/plans', user, params={'key': f'eq.{key}', 'limit': '1'}) or []
    if existing:
        rows = await _req('PATCH', '/plans', user, params={'key': f'eq.{key}'}, json=body, write=True)
    else:
        rows = await _req('POST', '/plans', user, json={'key': key, **body}, write=True)
    await log(user, 'admin_update', 'plan', key)
    return (rows or [{}])[0]


async def admin_create_professional(user: dict, data: dict) -> dict:
    await _require_admin(user)
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(500, 'Service role não configurado no servidor.')
    email = (data.get('email') or '').strip().lower()
    pw = data.get('password') or ''
    if '@' not in email or len(pw) < 6:
        raise HTTPException(400, 'E-mail válido e senha de no mínimo 6 caracteres são obrigatórios.')
    async with httpx.AsyncClient(timeout=20.0) as c:
        r = await c.post(f'{SUPABASE_URL}/auth/v1/admin/users',
            headers={'apikey': SUPABASE_SERVICE_ROLE_KEY,
                     'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
                     'Content-Type': 'application/json'},
            json={'email': email, 'password': pw, 'email_confirm': True,
                  'user_metadata': {'full_name': data.get('full_name') or ''}})
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f'Supabase: {r.text[:300]}')
    uid = r.json().get('id')
    patch = {}
    for k in ('professional_id', 'role', 'status', 'plan'):
        if data.get(k):
            patch[k] = data[k]
    if data.get('credits') is not None:
        patch['credits'] = int(data['credits'])
    if data.get('full_name'):
        patch['full_name'] = data['full_name']
    if patch:
        await _service_req('PATCH', '/profiles', params={'id': f'eq.{uid}'}, json=patch)
    await log(user, 'admin_create', 'profile', uid, {'email': email})
    return {'id': uid, 'email': email}


async def create_order(user: dict, pack_key: str) -> dict:
    from . import payments
    plan = await get_plan(user, pack_key)
    if not plan:
        raise HTTPException(400, 'Pacote inválido ou inativo.')
    rows = await _req('POST', '/orders', user, json={
        'pack': pack_key, 'credits': plan['credits'], 'amount_cents': plan['amount_cents'],
    }, write=True)
    order = (rows or [{}])[0]
    pref = await payments.create_preference(order['id'], {
        'nome': plan['name'], 'credits': plan['credits'], 'amount_cents': plan['amount_cents'],
    }, user.get('email', ''))
    await _req('PATCH', '/orders', user, params={'id': f'eq.{order["id"]}'},
               json={'provider_ref': pref['preference_id']}, write=True)
    await log(user, 'checkout', 'order', order['id'], {'pack': pack_key})
    return {'order_id': order['id'], 'init_point': pref['init_point']}


async def fulfill_payment(payment_id: str) -> dict:
    """Webhook do Mercado Pago. Idempotente."""
    from . import payments
    pay = await payments.get_payment(str(payment_id))
    if pay.get('status') != 'approved':
        return {'ignored': pay.get('status')}
    order_id = pay.get('external_reference')
    if not order_id:
        return {'ignored': 'sem external_reference'}
    rows = await _service_req('GET', '/orders', params={'id': f'eq.{order_id}', 'limit': '1'}) or []
    if not rows:
        return {'ignored': 'pedido não encontrado'}
    order = rows[0]
    if order['status'] == 'paid':
        return {'ok': True, 'already': True}
    await _service_req('PATCH', '/orders', params={'id': f'eq.{order_id}'},
                       json={'status': 'paid', 'provider_ref': str(payment_id)})
    await _service_req('POST', '/rpc/apply_credits', json={
        'p_owner': order['owner'], 'p_delta': order['credits'],
        'p_reason': 'purchase', 'p_ref': str(payment_id),
    })
    return {'ok': True, 'credits': order['credits']}


async def admin_grant_credits(user: dict, pid: str, delta: int) -> int:
    await _require_admin(user)
    return int(_scalar(await _service_req('POST', '/rpc/apply_credits', json={
        'p_owner': pid, 'p_delta': int(delta), 'p_reason': 'admin_grant',
    })) or 0)
