"""Autenticação via Supabase Auth.

Se SUPABASE_URL / SUPABASE_ANON_KEY não estiverem configurados, a autenticação
fica DESLIGADA e o app funciona como antes (uso local, sem login).

Quando ligada, cada requisição a /api/* precisa de um token JWT do Supabase no
cabeçalho Authorization: Bearer <token>. O token é validado chamando o endpoint
/auth/v1/user do próprio Supabase (fonte da verdade), com um cache curto.
"""
from __future__ import annotations

import os
import time

import httpx
from fastapi import Header, HTTPException

SUPABASE_URL = os.getenv('SUPABASE_URL', '').rstrip('/')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY', '').strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '').strip()
AUTH_ENABLED = bool(SUPABASE_URL and SUPABASE_ANON_KEY)

_LOCAL_USER = {'id': 'local', 'email': 'local', 'token': '', 'anon': True}

_cache: dict[str, tuple[float, dict]] = {}
_TTL = 90.0


def _bearer(authorization: str) -> str:
    if authorization and authorization[:7].lower() == 'bearer ':
        return authorization[7:].strip()
    return ''


async def _fetch_user(token: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f'{SUPABASE_URL}/auth/v1/user',
                headers={'Authorization': f'Bearer {token}', 'apikey': SUPABASE_ANON_KEY},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(503, f'Serviço de autenticação indisponível: {exc}') from exc
    if r.status_code != 200:
        raise HTTPException(401, 'Sessão inválida ou expirada. Faça login novamente.')
    try:
        return r.json()
    except ValueError as exc:
        raise HTTPException(502, 'Resposta inesperada do serviço de autenticação.') from exc


async def current_user(authorization: str = Header(default='')) -> dict:
    """Dependência FastAPI: retorna {id, email, token} do usuário autenticado."""
    if not AUTH_ENABLED:
        return dict(_LOCAL_USER)

    token = _bearer(authorization)
    if not token:
        raise HTTPException(401, 'Autenticação necessária.')

    now = time.time()
    cached = _cache.get(token)
    if cached and cached[0] > now:
        return cached[1]

    data = await _fetch_user(token)
    user = {
        'id': data.get('id'),
        'email': data.get('email') or data.get('phone') or data.get('id'),
        'token': token,
        'meta': data.get('user_metadata') or {},
    }
    _cache[token] = (now + _TTL, user)
    if len(_cache) > 1000:
        for k, (exp, _) in list(_cache.items()):
            if exp <= now:
                _cache.pop(k, None)
    return user


def public_config() -> dict:
    """Valores seguros para o frontend (a anon key é pública por design)."""
    return {
        'auth_enabled': AUTH_ENABLED,
        'supabase_url': SUPABASE_URL,
        'supabase_anon_key': SUPABASE_ANON_KEY,
    }
