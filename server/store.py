"""Persistência no Postgres do Supabase via PostgREST (sem driver de banco).

Todas as chamadas usam o JWT do usuário — as políticas RLS do Supabase
garantem que cada profissional só enxerga os próprios dados.
"""
from __future__ import annotations

import httpx
from fastapi import HTTPException

from .auth import AUTH_ENABLED, SUPABASE_ANON_KEY, SUPABASE_URL

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
    for k in ('full_name', 'professional_id', 'header', 'default_model'):
        if k in data:
            body[k] = data[k]
    rows = await _req('POST', '/profiles', user, json=body, write=True)
    return (rows or [{}])[0]


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
