"""Protocolo item a item a partir da própria planilha de correção.

Muitas abas da planilha já trazem cada item do protocolo (texto do item + célula
de resposta) e pontuam a resposta com fórmulas do tipo
    IF(H17="","", IF(H17="DT",6, IF(H17="D",5, ...)))
Este módulo só LÊ esse layout: acha as células de resposta, as opções aceitas
(os códigos entre aspas da fórmula), o texto do item e a seção. A tela usa isso
para mostrar o protocolo; quem pontua continua sendo a planilha — nenhuma
fórmula é criada ou alterada.
"""
from __future__ import annotations

import re
from collections import OrderedDict

_REF = r'\$?([A-Z]{1,3})\$?(\d+)'
_CMP = re.compile(r'(?<![A-Z$])' + _REF + r'\s*=\s*"([^"]*)"')
_MIN_ITEMS = 5


def _col_num(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + ord(ch) - 64
    return n


def _col_name(n: int) -> str:
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def detect(rows: dict) -> dict | None:
    """rows = WorkbookEngine._sheet_rows(sheet). Devolve o protocolo ou None."""
    options: dict[tuple[int, int], list[str]] = {}
    for r, cols in rows.items():
        for c, cell in cols.items():
            f = cell.get('formula') or ''
            if '="' not in f:
                continue
            for col, row, code in _CMP.findall(f):
                key = (int(row), _col_num(col))
                opts = options.setdefault(key, [])
                if code and code not in opts:
                    opts.append(code)
    # resposta = célula sem fórmula (entrada), com 2+ opções
    # (códigos curtos: DT/D/CP, N/P/B/D, S/N… — exclui seletores de tabela normativa)
    inputs = {k: v for k, v in options.items()
              if 2 <= len(v) <= 8 and all(0 < len(o) <= 3 for o in v)
              and not (rows.get(k[0], {}).get(k[1], {}).get('formula'))}
    if len(inputs) < _MIN_ITEMS:
        return None

    by_row: dict[int, list[int]] = {}
    for (r, c) in inputs:
        by_row.setdefault(r, []).append(c)
    first_input_col = min(c for (_, c) in inputs)

    def row_text(r: int, before: int, numbered: bool = False) -> str:
        best, num = '', None
        for c, cell in sorted(rows.get(r, {}).items()):
            if c >= before:
                break
            v = cell.get('value')
            if cell.get('formula'):
                continue
            if isinstance(v, str) and len(v.strip()) > len(best):
                best = v.strip()
            elif numbered and num is None and isinstance(v, (int, float)) and float(v).is_integer() and 0 < v < 1000:
                num = int(v)
        if numbered and num is not None:
            return f'{num}. {best}' if best and not best.startswith(str(num)) else (best or f'Item {num}')
        return best

    items, section = [], ''
    item_rows = sorted(by_row)
    for r in range(min(item_rows) - 3, max(item_rows) + 1):
        if r not in by_row:
            t = row_text(r, first_input_col)
            if t and len(t) <= 80:
                section = t
            continue
        cols = sorted(by_row[r])
        label = row_text(r, cols[0], numbered=True) or f'Item {len(items) + 1}'
        opts = inputs[(r, cols[0])]
        items.append({'row': r, 'label': label, 'section': section,
                      'cells': [f'{_col_name(c)}{r}' for c in cols], 'options': opts})
    if len(items) < _MIN_ITEMS:
        return None
    n_inf = max(len(i['cells']) for i in items)
    # nome de cada coluna de resposta (respondente): texto acima, na mesma coluna
    first_row = items[0]['row']
    resp_cols = sorted({_col_num(re.match(r'[A-Z]+', c).group()) for i in items for c in i['cells']})
    skip = {'resposta', 'nota', 'pontuação', 'valor', 'item', 'itens'}
    informants = []
    for k, c in enumerate(resp_cols):
        name = ''
        for rr in range(first_row - 1, max(first_row - 8, 0), -1):
            v = rows.get(rr, {}).get(c, {}).get('value')
            bad = (not isinstance(v, str) or not v.strip() or v.strip().lower() in skip or v.strip().lower() == 'empty'
                   or v.strip().lower().startswith(('respostas', 'para maiores')) or len(v.strip()) > 30)
            if not bad and not rows[rr][c].get('formula'):
                name = v.strip(); break
        informants.append(name or f'Respondente {k + 1}')
    # campo de identificação de cada respondente: o cabeçalho da coluna costuma ser
    # IF($J$11="","",$J$11) — sem ele preenchido a planilha não calcula os fatores.
    _HDR = re.compile(r'IF\(\$?([A-Z]{1,3})\$?(\d+)\s*=\s*""\s*,\s*""\s*,\s*\$?\1\$?\2\s*\)')
    id_cells = []
    for c in resp_cols:
        found = ''
        for rr in range(first_row - 1, max(first_row - 8, 0), -1):
            m = _HDR.search(rows.get(rr, {}).get(c, {}).get('formula') or '')
            if m:
                found = f'{m.group(1)}{m.group(2)}'; break
        id_cells.append(found)
    sections = list(OrderedDict.fromkeys(i['section'] for i in items))
    return {'items': items, 'informants': n_inf, 'informant_names': informants[:n_inf],
            'informant_cells': id_cells[:n_inf], 'sections': sections}


def input_cells(proto: dict) -> set[str]:
    return {c for i in proto['items'] for c in i['cells']} | {c for c in proto.get('informant_cells', []) if c}


# Abas liberadas depois de conferidas (itens marcados → mesma tabela que digitar o PB).
ENABLED = {'ETDAH-2', 'SNAP-IV', 'SDQ-Pr', 'BRIEF-P'}


def detect_selectors(rows: dict) -> list[dict]:
    """Seletores de tabela normativa / amostra: células de entrada vazias que as
    fórmulas comparam com textos longos (ex.: Q3 = "Amostra Geral" | "Tipo de Escola").
    Viram parâmetros com lista de opções; padrão em branco = comportamento de antes."""
    options: dict[tuple[int, int], list[str]] = {}
    for r, cols in rows.items():
        for c, cell in cols.items():
            f = cell.get('formula') or ''
            if '="' not in f:
                continue
            for col, row, code in _CMP.findall(f):
                key = (int(row), _col_num(col))
                opts = options.setdefault(key, [])
                if code and code not in opts:
                    opts.append(code)
    out = []
    for (r, c), opts in sorted(options.items()):
        cell = rows.get(r, {}).get(c, {})
        if cell.get('formula') or len(opts) < 2 or len(opts) > 25 or not any(len(o) > 3 for o in opts):
            continue
        label = ''
        for cc in range(c - 1, 0, -1):
            v = rows.get(r, {}).get(cc, {}).get('value')
            if isinstance(v, str) and v.strip() and not rows[r][cc].get('formula'):
                label = v.strip().rstrip(':'); break
        if r > 8 or not label or label.lower() == 'empty':
            continue  # seletores ficam no cabeçalho; o resto são itens
        base = cell.get('value')
        current = '' if base is None or str(base).strip().lower() == 'empty' else str(base).strip()  # valor salvo na planilha
        if current and current not in opts:
            opts = [current] + opts
        out.append({'cell': f'{_col_name(c)}{r}', 'label': label, 'options': opts,
                    'current': current, 'selector': True})
    return out
