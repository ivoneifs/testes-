"""Persistência no Postgres do Supabase via PostgREST (sem driver de banco).

Todas as chamadas usam o JWT do usuário — as políticas RLS do Supabase
garantem que cada profissional só enxerga os próprios dados.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException

from .auth import AUTH_ENABLED, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

REST = f'{SUPABASE_URL}/rest/v1' if SUPABASE_URL else ''
TRIAL_DAYS = 14


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
        'external_results': payload.get('external_results') or [],
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
_PRO_FIELDS = 'id,full_name,email,professional_id,role,status,plan,credits,trial_ends_at,created_at,updated_at'
_PRO_EDITABLE = ('full_name', 'professional_id', 'role', 'status', 'plan', 'credits')


async def list_professionals(user: dict) -> list[dict]:
    await _require_admin(user)
    return await _req('GET', '/profiles', user, params={
        'select': _PRO_FIELDS, 'order': 'created_at.desc', 'limit': '1000',
    }) or []


def _access_patch(data: dict) -> dict:
    """Tipo de acesso escolhido pelo admin → campos do perfil.

    admin → role admin · pro → profissional sem prazo · trial → profissional
    com acesso até hoje + trial_days (padrão 14).
    """
    access = data.get('access')
    if access == 'admin':
        return {'role': 'admin', 'trial_ends_at': None}
    if access == 'pro':
        return {'role': 'professional', 'trial_ends_at': None}
    if access == 'trial':
        days = data.get('trial_days')
        days = TRIAL_DAYS if days is None else max(0, int(days))
        ends = datetime.now(timezone.utc) + timedelta(days=days)
        return {'role': 'professional', 'trial_ends_at': ends.isoformat()}
    return {}


def access_state(profile: dict) -> dict:
    """{'trial': bool, 'trial_days_left': int|None, 'blocked': str|None} para o perfil."""
    out = {'trial': False, 'trial_days_left': None, 'blocked': None}
    if profile.get('role') == 'admin':
        return out
    if profile.get('status') == 'suspended':
        out['blocked'] = 'suspended'
    elif profile.get('status') == 'pending':
        out['blocked'] = 'pending'      # cadastro novo: aguardando o administrador liberar
        return out
    ends = profile.get('trial_ends_at')
    if ends:
        end = datetime.fromisoformat(str(ends).replace('Z', '+00:00'))
        secs = (end - datetime.now(timezone.utc)).total_seconds()
        out['trial'] = True
        out['trial_days_left'] = max(0, math.ceil(secs / 86400))
        if secs <= 0:
            out['blocked'] = out['blocked'] or 'trial_expired'
    return out


async def admin_update_professional(user: dict, pid: str, data: dict) -> dict:
    await _require_admin(user)
    body = {k: data[k] for k in _PRO_EDITABLE if data.get(k) is not None}
    body.update(_access_patch(data))
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
    body = {k: data.get(k) for k in ('name', 'birth_date', 'sex', 'education', 'notes', 'dados', 'anamnese')}
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


# Custo de cada serviço, em créditos (1 crédito = R$ 20).
COST_TESTE = 1.0      # correção de um teste
COST_HISTORIA = 1.0   # História de Vida (análise da anamnese)
COST_LAUDO = 1.0      # laudo (Avaliação Completa ou Geração de Laudo)
NO_CREDITS = 'Créditos insuficientes: {need} crédito(s) para este serviço. Compre um pacote em Planos para continuar.'


def _num(v) -> float:
    return float(v or 0)


async def credit_balance(user: dict) -> float:
    return _num((await get_profile(user)).get('credits'))


async def spend_laudo(user: dict, ref: str | None = None) -> float:
    """Consome 1 crédito (admin é ilimitado). 402 se não houver saldo."""
    try:
        return _num(_scalar(await _req('POST', '/rpc/spend_laudo', user, json={'p_ref': ref}, write=True)))
    except HTTPException as e:
        if 'insufficient_credits' in str(e.detail):
            raise HTTPException(402, NO_CREDITS.format(need='1'))
        raise


async def spend_credits(user: dict, amount: float, reason: str, ref: str | None = None) -> float:
    """Debita `amount` créditos. Com `ref`, o mesmo serviço repetido no mesmo dia sai de graça."""
    try:
        return _num(_scalar(await _req('POST', '/rpc/spend_credits', user, write=True, json={
            'p_amount': amount, 'p_reason': reason, 'p_ref': ref})))
    except HTTPException as e:
        if 'insufficient_credits' in str(e.detail):
            raise HTTPException(402, NO_CREDITS.format(need=f'{amount:g}'.replace('.', ',')))
        raise


async def can_spend(user: dict, amount: float) -> bool:
    p = await get_profile(user)
    return p.get('role') == 'admin' or _num(p.get('credits')) >= amount


async def can_laudo(user: dict) -> bool:
    return await can_spend(user, COST_LAUDO)


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
    patch = _access_patch(data) if data.get('access') else {}
    for k in ('professional_id', 'role', 'status', 'plan'):
        if data.get(k):
            patch[k] = data[k]
    if data.get('credits') is not None:
        patch['credits'] = float(data['credits'])
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
    # quem compra deixa de ser conta de teste
    await _service_req('PATCH', '/profiles', params={'id': f'eq.{order["owner"]}'},
                       json={'trial_ends_at': None})
    return {'ok': True, 'credits': order['credits']}


async def admin_grant_credits(user: dict, pid: str, delta: float) -> float:
    await _require_admin(user)
    return _num(_scalar(await _service_req('POST', '/rpc/apply_credits', json={
        'p_owner': pid, 'p_delta': int(delta), 'p_reason': 'admin_grant',
    })) or 0)


async def admin_delete_plan(user: dict, key: str) -> None:
    await _require_admin(user)
    await _req('DELETE', '/plans', user, params={'key': f'eq.{key}'})
    await log(user, 'admin_delete', 'plan', key)


async def admin_set_password(user: dict, pid: str, password: str) -> None:
    """Define uma nova senha para qualquer usuário (Auth Admin API)."""
    await _require_admin(user)
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(500, 'Service role não configurado no servidor.')
    if len(password or '') < 6:
        raise HTTPException(400, 'A senha precisa ter no mínimo 6 caracteres.')
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.put(f'{SUPABASE_URL}/auth/v1/admin/users/{pid}',
            headers={'apikey': SUPABASE_SERVICE_ROLE_KEY,
                     'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
                     'Content-Type': 'application/json'},
            json={'password': password})
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f'Supabase: {r.text[:300]}')
    await log(user, 'admin_password', 'profile', pid)


# ---------- aparência do site (cores + textos da landing) ----------
async def get_site() -> dict:
    """Leitura pública (anon key): a landing e o app aplicam as cores daqui."""
    if not SUPABASE_URL:
        return {}
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(f'{REST}/site_settings', params={'id': 'eq.site', 'select': 'data'},
                            headers={'apikey': SUPABASE_ANON_KEY, 'Authorization': f'Bearer {SUPABASE_ANON_KEY}'})
        rows = r.json() if r.status_code < 400 and r.content else []
        return (rows[0].get('data') if rows else None) or {}
    except (httpx.HTTPError, ValueError):
        return {}


async def update_site(user: dict, data: dict) -> dict:
    await _require_admin(user)
    rows = await _req('PATCH', '/site_settings', user, params={'id': 'eq.site'},
                      json={'data': data}, write=True)
    await log(user, 'admin_update', 'site', 'site')
    return (rows or [{}])[0].get('data') or data


# ---------- vídeos explicativos (links) ----------
_VIDEO_FIELDS = ('title', 'test', 'url', 'description', 'sort')


async def list_videos(user: dict) -> list[dict]:
    return await _req('GET', '/videos', user, params={'select': '*', 'order': 'sort,title'}) or []


async def admin_save_video(user: dict, data: dict, vid: str | None = None) -> dict:
    await _require_admin(user)
    body = {k: data[k] for k in _VIDEO_FIELDS if data.get(k) is not None}
    url = (body.get('url') or '').strip()
    if url and not url.lower().startswith(('https://', 'http://')):
        raise HTTPException(400, 'O link precisa começar com https://')
    if vid:
        rows = await _req('PATCH', '/videos', user, params={'id': f'eq.{vid}'}, json=body, write=True)
    else:
        if not body.get('title') or not url:
            raise HTTPException(400, 'Título e link são obrigatórios.')
        rows = await _req('POST', '/videos', user, json=body, write=True)
    await log(user, 'admin_update', 'video', vid)
    return (rows or [{}])[0]


async def admin_delete_video(user: dict, vid: str) -> None:
    await _require_admin(user)
    await _req('DELETE', '/videos', user, params={'id': f'eq.{vid}'})
    await log(user, 'admin_delete', 'video', vid)


# ---------- testes realizados (um por paciente + teste) ----------
HISTORIA_TEST = 'História de Vida'


def patient_key(p: dict) -> str:
    import unicodedata
    name = unicodedata.normalize('NFKD', str(p.get('name') or '')).encode('ascii', 'ignore').decode()
    return (' '.join(name.lower().split()) or 'sem-nome') + '|' + str(p.get('birth_date') or '')


async def list_test_results(user: dict, key: str | None = None) -> list[dict]:
    params = {'select': '*', 'order': 'updated_at.desc', 'limit': '1000'}
    if key:
        params['patient_key'] = f'eq.{key}'
    return await _req('GET', '/test_results', user, params=params) or []


async def save_test_result(user: dict, data: dict, rid: str | None = None) -> dict:
    p = data.get('patient') or {}
    if not data.get('test'):
        raise HTTPException(400, 'Informe o teste.')
    body = {'patient': p, 'patient_key': patient_key(p), 'patient_id': data.get('patient_id'),
            'test': data['test'], 'inputs': data.get('inputs') or {}, 'result': data.get('result') or {}}
    if rid:
        rows = await _req('PATCH', '/test_results', user, params={'id': f'eq.{rid}'}, json=body, write=True)
    else:
        h = {'on_conflict': 'owner,patient_key,test'}
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.post(f'{REST}/test_results', params=h, json={**body, 'owner': user['id']},
                             headers={**_headers(user, write=True),
                                      'Prefer': 'return=representation,resolution=merge-duplicates'})
        if r.status_code >= 400:
            raise HTTPException(r.status_code, f'Supabase: {r.text[:300]}')
        rows = r.json()
    return (rows or [{}])[0]


async def delete_test_result(user: dict, rid: str) -> None:
    await _req('DELETE', '/test_results', user, params={'id': f'eq.{rid}'})
