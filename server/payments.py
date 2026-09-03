"""Integração Mercado Pago (Checkout Pro) para compra de créditos de laudo."""
from __future__ import annotations

import os

import httpx
from fastapi import HTTPException

MP_TOKEN = os.getenv('MERCADOPAGO_ACCESS_TOKEN', '').strip()
MP_BASE = 'https://api.mercadopago.com'
PUBLIC_URL = os.getenv('PUBLIC_URL', 'https://neuro-testes.appsbrasil.store').rstrip('/')

# pack -> créditos e preço (centavos de BRL)
PACKS = {
    'inicial':      {'nome': 'Pack Inicial',         'credits': 5,  'amount_cents': 4900},
    'profissional': {'nome': 'Pack Profissional',    'credits': 20, 'amount_cents': 14900},
    'premium':      {'nome': 'Pack Clínica Premium', 'credits': 50, 'amount_cents': 29900},
}


def enabled() -> bool:
    return bool(MP_TOKEN)


async def create_preference(order_id: str, pack: dict, payer_email: str) -> dict:
    if not MP_TOKEN:
        raise HTTPException(400, 'Pagamento não configurado no servidor (MERCADOPAGO_ACCESS_TOKEN).')
    body = {
        'items': [{
            'title': f"NeuroScore — {pack['nome']} ({pack['credits']} laudos)",
            'quantity': 1, 'currency_id': 'BRL',
            'unit_price': round(pack['amount_cents'] / 100, 2),
        }],
        'external_reference': order_id,
        'metadata': {'payer_email': payer_email} if payer_email else {},
        'back_urls': {
            'success': f'{PUBLIC_URL}/#planos?pago=1',
            'failure': f'{PUBLIC_URL}/#planos?pago=0',
            'pending': f'{PUBLIC_URL}/#planos?pago=pend',
        },
        'auto_return': 'approved',
        'notification_url': f'{PUBLIC_URL}/api/webhooks/mercadopago',
        'statement_descriptor': 'NEUROSCORE',
    }
    async with httpx.AsyncClient(timeout=20.0) as c:
        r = await c.post(f'{MP_BASE}/checkout/preferences', json=body,
                         headers={'Authorization': f'Bearer {MP_TOKEN}'})
    if r.status_code >= 400:
        raise HTTPException(502, f'Mercado Pago: {r.text[:300]}')
    d = r.json()
    return {'preference_id': d['id'],
            'init_point': d.get('init_point') or d.get('sandbox_init_point')}


async def get_payment(payment_id: str) -> dict:
    if not MP_TOKEN:
        raise HTTPException(400, 'Pagamento não configurado.')
    async with httpx.AsyncClient(timeout=20.0) as c:
        r = await c.get(f'{MP_BASE}/v1/payments/{payment_id}',
                        headers={'Authorization': f'Bearer {MP_TOKEN}'})
    if r.status_code >= 400:
        raise HTTPException(502, f'Mercado Pago: {r.text[:200]}')
    return r.json()
