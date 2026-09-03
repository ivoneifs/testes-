"""Ajustes de compatibilidade com o Excel para a biblioteca `formulas`.

O Excel faz coerção implícita de texto para número em contexto aritmético:
`"7,5%"` vira 0,075, `"1,5"` vira 1,5 (locale pt-BR) e célula vazia vira 0.
A `formulas` chama `float()` direto e devolve #VALUE! nesses casos — o que
quebra cadeias de cálculo reais (ex.: WSCT48-R, onde um campo de % é texto e
alimenta o z-score). Aqui reescrevemos os operadores aritméticos com um
`input_parser` que replica a coerção do Excel; qualquer string que não seja
numérica continua gerando #VALUE! como antes.
"""
from __future__ import annotations

import functools
import re

import schedula as sh

_PCT_RE = re.compile(r'^\s*(-?\d+(?:[.,]\d+)?)\s*%\s*$')
_NUM_RE = re.compile(r'^\s*(-?\d+(?:[.,]\d+)?)\s*$')

_patched = False


def _to_number(x):
    if x is sh.EMPTY or x is None or x == '':
        return 0.0
    if isinstance(x, bool):
        return 1.0 if x else 0.0
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        m = _PCT_RE.match(x)
        if m:
            return float(m.group(1).replace(',', '.')) / 100.0
        m = _NUM_RE.match(x)
        if m:
            return float(m.group(1).replace(',', '.'))
    return float(x)  # não-numérico: deixa estourar -> #VALUE! (comportamento original)


def _num_parser(*args):
    return map(_to_number, args)


def patch() -> None:
    """Idempotente. Chamar antes de compilar qualquer fórmula."""
    global _patched
    if _patched:
        return
    from formulas.functions import operators as _ops, wrap_ufunc, get_functions
    from formulas.functions import FUNCTIONS, Error

    arith = {
        '+': lambda x, y: x + y,
        '-': lambda x, y: x - y,
        'U-': lambda x: -x,
        '*': lambda x, y: x * y,
        '/': lambda x, y: (x / y) if y else Error.errors['#DIV/0!'],
        '^': lambda x, y: x ** y,
    }
    for sym, fn in arith.items():
        _ops.OPERATORS[sym] = wrap_ufunc(fn, input_parser=_num_parser)

    # Funções que a `formulas` 1.3.3 não implementa e as planilhas usam.
    FUNCTIONS['QUOTIENT'] = wrap_ufunc(
        lambda a, b: Error.errors['#DIV/0!'] if b == 0 else int(a / b)
    )
    get_functions.cache_clear()
    _patched = True
