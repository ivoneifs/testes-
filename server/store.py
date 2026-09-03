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
async def list_evaluations(user: dict) -> list[dict]:
    return await _req('GET', '/evaluations', user, params={
        'select': 'id,patient,tests,integrated_report,created_at,updated_at',
        'order': 'updated_at.desc',
        'limit': '200',
    }) or []


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
