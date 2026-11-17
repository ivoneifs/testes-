"""Recuperação de senha por código de 6 dígitos enviado no WhatsApp cadastrado."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException

from . import notify, store
from .auth import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

CODE_TTL_MIN = 15
MAX_ATTEMPTS = 5
MAX_PER_HOUR = 3
_PEPPER = (SUPABASE_SERVICE_ROLE_KEY or os.getenv('RESET_PEPPER', 'neuroscore'))[:64]


def available() -> bool:
    return notify.enabled() and bool(SUPABASE_SERVICE_ROLE_KEY)


def _hash(user_id: str, code: str) -> str:
    return hmac.new(_PEPPER.encode(), f'{user_id}:{code}'.encode(), hashlib.sha256).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _find(email: str) -> dict | None:
    email = (email or '').strip().lower()
    if '@' not in email:
        return None
    rows = await store._service_req('GET', '/profiles', params={
        'email': f'ilike.{email}', 'select': 'id,email,phone,full_name,status', 'limit': '1'}) or []
    return rows[0] if rows else None


def _mask(phone: str) -> str:
    d = notify.normalize(phone)
    return f'(**) *****-{d[-4:]}' if d else ''


async def start(email: str) -> dict:
    """Sempre responde igual (não revela se o e-mail existe)."""
    generic = {'ok': True, 'message': 'Se o e-mail estiver cadastrado com WhatsApp, você receberá um código em instantes.'}
    if not available():
        raise HTTPException(503, 'Recuperação automática indisponível no momento. Fale com o suporte pelo WhatsApp.')
    prof = await _find(email)
    if not prof or not notify.normalize(prof.get('phone')):
        return generic
    since = (_now() - timedelta(hours=1)).isoformat()
    recent = await store._service_req('GET', '/password_resets', params={
        'user_id': f'eq.{prof["id"]}', 'created_at': f'gte.{since}', 'select': 'id'}) or []
    if len(recent) >= MAX_PER_HOUR:
        return generic
    code = f'{secrets.randbelow(1_000_000):06d}'
    await store._service_req('POST', '/password_resets', json={
        'user_id': prof['id'], 'code_hash': _hash(prof['id'], code),
        'expires_at': (_now() + timedelta(minutes=CODE_TTL_MIN)).isoformat()})
    nome = (prof.get('full_name') or '').split(' ')[0]
    ok = await notify.send_whatsapp(prof['phone'], (
        f'NeuroScore 🔐\n\nOlá{(", " + nome) if nome else ""}! Seu código para criar uma nova senha é:\n\n*{code}*\n\n'
        f'Ele vale por {CODE_TTL_MIN} minutos. Se você não pediu, ignore esta mensagem.'))
    return {**generic, 'sent_to': _mask(prof['phone']) if ok else ''}


async def confirm(email: str, code: str, password: str) -> dict:
    bad = HTTPException(400, 'Código inválido ou expirado. Peça um novo código.')
    if len(password or '') < 8:
        raise HTTPException(400, 'A nova senha precisa ter pelo menos 8 caracteres.')
    code = ''.join(ch for ch in (code or '') if ch.isdigit())
    prof = await _find(email)
    if not prof or len(code) != 6:
        raise bad
    rows = await store._service_req('GET', '/password_resets', params={
        'user_id': f'eq.{prof["id"]}', 'used_at': 'is.null', 'expires_at': f'gt.{_now().isoformat()}',
        'order': 'created_at.desc', 'limit': '1'}) or []
    if not rows:
        raise bad
    row = rows[0]
    if row['attempts'] >= MAX_ATTEMPTS:
        raise HTTPException(429, 'Muitas tentativas. Peça um novo código.')
    if not hmac.compare_digest(row['code_hash'], _hash(prof['id'], code)):
        await store._service_req('PATCH', '/password_resets', params={'id': f'eq.{row["id"]}'},
                                 json={'attempts': row['attempts'] + 1})
        raise bad
    used = await store._service_req('PATCH', '/password_resets',
                                    params={'id': f'eq.{row["id"]}', 'used_at': 'is.null'},
                                    json={'used_at': _now().isoformat()}) or []
    if not used:
        raise bad
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.put(f'{SUPABASE_URL}/auth/v1/admin/users/{prof["id"]}',
                        headers={'apikey': SUPABASE_SERVICE_ROLE_KEY,
                                 'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
                                 'Content-Type': 'application/json'},
                        json={'password': password})
    if r.status_code >= 400:
        raise HTTPException(502, 'Não foi possível salvar a nova senha. Tente de novo.')
    await notify.send_whatsapp(prof.get('phone'), 'NeuroScore 🔐\n\nSua senha foi alterada agora. Se não foi você, fale com o suporte imediatamente.')
    return {'ok': True}
