"""Avisos por WhatsApp via WAHA (WhatsApp HTTP API).

Configuração (env do app no Coolify):
  WAHA_URL        ex.: https://waha.seudominio.com   (sem barra no fim)
  WAHA_API_KEY    chave X-Api-Key do WAHA
  WAHA_SESSION    nome da sessão conectada (padrão: default)
  ADMIN_WHATSAPP  número que recebe os avisos do sistema (padrão: 5574988259925)
Sem WAHA_URL/WAHA_API_KEY os avisos ficam desligados (nada quebra).
"""
from __future__ import annotations

import logging
import os
import re

import httpx

log = logging.getLogger('neuroscore.notify')

WAHA_URL = os.getenv('WAHA_URL', '').rstrip('/')
WAHA_API_KEY = os.getenv('WAHA_API_KEY', '').strip()
WAHA_SESSION = os.getenv('WAHA_SESSION', 'default').strip() or 'default'
ADMIN_WHATSAPP = re.sub(r'\D', '', os.getenv('ADMIN_WHATSAPP', '5574988259925'))


def enabled() -> bool:
    return bool(WAHA_URL and WAHA_API_KEY)


def normalize(phone: str | None) -> str:
    """Só dígitos, com DDI 55 quando vier só DDD + número."""
    d = re.sub(r'\D', '', phone or '')
    if 10 <= len(d) <= 11:
        d = '55' + d
    return d if 12 <= len(d) <= 13 else ''


async def _chat_id(client: httpx.AsyncClient, phone: str) -> str:
    # O WhatsApp de alguns números BR não tem o 9º dígito: o WAHA descobre o id certo.
    try:
        r = await client.get(f'{WAHA_URL}/api/contacts/check-exists',
                             params={'phone': phone, 'session': WAHA_SESSION})
        j = r.json() if r.status_code == 200 else {}
        if j.get('numberExists') and j.get('chatId'):
            return j['chatId']
    except (httpx.HTTPError, ValueError):
        pass
    return f'{phone}@c.us'


async def send_whatsapp(phone: str | None, text: str) -> bool:
    """Envia texto. Devolve True se o WAHA aceitou; nunca levanta exceção."""
    num = normalize(phone)
    if not (enabled() and num):
        return False
    try:
        async with httpx.AsyncClient(timeout=15.0, headers={'X-Api-Key': WAHA_API_KEY}) as c:
            chat = await _chat_id(c, num)
            r = await c.post(f'{WAHA_URL}/api/sendText',
                             json={'session': WAHA_SESSION, 'chatId': chat, 'text': text})
        if r.status_code >= 400:
            log.warning('WAHA sendText %s: %s', r.status_code, r.text[:200])
            return False
        return True
    except httpx.HTTPError as exc:
        log.warning('WAHA indisponível: %s', exc)
        return False


async def notify_admin(text: str) -> bool:
    return await send_whatsapp(ADMIN_WHATSAPP, text)
