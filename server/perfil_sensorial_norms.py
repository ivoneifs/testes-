"""Normas do Perfil Sensorial 2 (Sensory Profile 2) — classificação em 5 bandas.

A planilha de correção só calcula pontuação bruta, razão e um STATUS de 2 bandas
(e com pontos de corte ERRADOS — ex.: Criança/Exploração a planilha usa
"como a maioria = 23–33", mas o manual, Fig. 4.8, diz 20–47). Aqui ficam as
normas do manual do usuário, usadas para produzir a classificação correta e a
faixa de percentil de cada quadrante/seção/fator.

═══════════════════════════════════════════════════════════════════════════════
COMO PREENCHER (basta digitar números — não precisa mexer em mais nada)

CUTOFFS[forma][escala] = [a, b, c, d]
    são os LIMITES SUPERIORES das 4 primeiras bandas (a 5ª é "tudo acima de d"):

        bruto <= a          → Muito menos que os outros
        a < bruto <= b      → Menos que os outros
        b < bruto <= c      → Exatamente como a maioria dos outros
        c < bruto <= d      → Mais que os outros
        bruto > d           → Muito mais que os outros

    Exemplo do manual (Fig. 4.8, Criança / Exploração):
        Muito menos 0–6 | Menos 7–19 | Como a maioria 20–47 | Mais 48–60 | Muito mais 61–95
        →  "EXPLORAÇÃO": [6, 19, 47, 60]

    Deixe  None  enquanto não tiver os números — a escala aparece sem classificação.

Os nomes das escalas podem ser digitados com acento/maiúscula à vontade; a busca
ignora acento e caixa. Rode  `python -m server.perfil_sensorial_norms`  para ver
o que ainda falta.
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import unicodedata

BANDS = [
    'Muito menos que os outros',
    'Menos que os outros',
    'Exatamente como a maioria dos outros',
    'Mais que os outros',
    'Muito mais que os outros',
]

# ───────────────────────── FAIXAS DE CORTE (pontuação bruta → banda) ──────────
# [limite_MuitoMenos, limite_Menos, limite_ComoAMaioria, limite_Mais]
CUTOFFS: dict[str, dict[str, list[int] | None]] = {
    'Criança': {
        # Quadrantes — manual Fig. 4.8  ✅ (conferir)
        'EXPLORAÇÃO':      [6, 19, 47, 60],
        'ESQUIVA':         [7, 20, 46, 59],
        'SENSIBILIDADE':   [6, 17, 42, 53],
        'OBSERVAÇÃO':      [6, 18, 43, 55],
        # Seções sensoriais e comportamentais — PREENCHER (ficha de resumo da Criança)
        'Auditivo':        None,
        'Visual':          None,
        'Tato':            None,
        'Movimentos':      None,
        'Posição do Corpo': None,
        'Oral':            None,
        'Conduta':         None,
        'Socioemocional':  None,
        'Atenção':         None,
    },
    'Criança Pequena': {
        # Quadrantes — PREENCHER (ficha de resumo da Criança Pequena)
        'EXPLORAÇÃO':      None,
        'ESQUIVA':         None,
        'SENSIBILIDADE':   None,
        'OBSERVAÇÃO':      None,
        # Seções — manual Fig. 4.11  ✅ (conferir; leitura em baixa resolução)
        'Geral':           [5, 10, 22, 27],
        'Auditivo':        [2, 6, 14, 17],
        'Visual':          [5, 10, 19, 24],
        'Tato':            [1, 5, 13, 16],
        'Movimentos':      [9, 12, 20, 23],
        'Oral':            [1, 5, 15, 19],
        'Comportamental':  [3, 6, 14, 17],
    },
    'Bebê': {
        # manual Fig. 4.13  ✅ (conferir)
        'PONTUAÇÃO TOTAL DO BEBÊ': [30, 40, 61, 71],
    },
    'Professor': {
        # Quadrantes — PREENCHER (ficha de resumo do Acompanhamento Escolar)
        'EXPLORAÇÃO':      None,
        'ESQUIVA':         None,
        'SENSIBILIDADE':   None,
        'OBSERVAÇÃO':      None,
        # Seções — PREENCHER
        'Auditivo':        None,
        'Visual':          None,
        'Tato':            None,
        'Movimentos':      None,
        'Comportamental':  None,
        # Fatores escolares — manual Fig. 4.10 (CONFERIR com atenção; leitura difícil)
        'Fator 1':         None,
        'Fator 2':         None,
        'Fator 3':         None,
        'Fator 4':         None,
    },
    'Abreviado': {
        # PREENCHER (ficha de resumo do Abreviado)
        'EXPLORAÇÃO':      None,
        'ESQUIVA':         None,
        'SENSIBILIDADE':   None,
        'OBSERVAÇÃO':      None,
        'Sensorial':       None,
        'Comportamental':  None,
    },
}

# ───────────────────────── FAIXAS DE PERCENTIL (Anexo A do manual) ────────────
# 5 strings, uma por banda, na mesma ordem de BANDS. "" = sem pontuação nessa faixa.
PERCENTIS: dict[str, dict[str, list[str]]] = {
    'Bebê': {
        'PONTUAÇÃO TOTAL DO BEBÊ': ['<1', '1-16', '17-85', '86-96', '97-99'],
    },
    'Criança Pequena': {
        'EXPLORAÇÃO':      ['1-3', '4-13', '14-84', '85-99', ''],
        'ESQUIVA':         ['1-3', '4-5', '6-87', '88-95', '96-99'],
        'SENSIBILIDADE':   ['1-2', '3-5', '6-86', '87-97', '98-99'],
        'OBSERVAÇÃO':      ['1-3', '4-7', '8-89', '90-95', '96-99'],
        'Geral':           ['<1', '1-5', '6-88', '89-96', '97-99'],
        'Auditivo':        ['1-2', '3-6', '7-87', '88-95', '96-99'],
        'Visual':          ['<1', '1-13', '14-83', '84-98', '99'],
        'Tato':            ['1-2', '3-5', '6-87', '88-95', '96-99'],
        'Movimentos':      ['1-2', '3-11', '12-89', '90-99', '>99'],
        'Oral':            ['<1', '1-7', '8-88', '89-97', '98-99'],
        'Comportamental':  ['1-2', '3-6', '7-86', '87-95', '96-99'],
    },
    'Criança': {
        'EXPLORAÇÃO':      ['1-2', '3-8', '9-84', '85-97', '98-99'],
        'ESQUIVA':         ['1-2', '3-7', '8-86', '87-96', '97-99'],
        'SENSIBILIDADE':   ['1-2', '3-8', '9-86', '87-96', '97-99'],
        'OBSERVAÇÃO':      ['1-2', '3-8', '9-86', '87-96', '97-99'],
        'Auditivo':        ['<1', '1-11', '12-85', '86-96', '97-99'],
        'Visual':          ['1-2', '3-10', '11-82', '83-98', '99'],
        'Tato':            ['1', '2-10', '11-87', '88-96', '97-99'],
        'Movimentos':      ['1-2', '3-7', '8-85', '86-96', '97-99'],
        'Posição do Corpo': ['1', '2-9', '10-89', '90-96', '97-99'],
        'Oral':            ['', '1-7', '8-87', '88-95', '96-99'],
        'Conduta':         ['<1', '1-5', '6-84', '85-96', '97-99'],
        'Socioemocional':  ['1-2', '3-8', '9-85', '86-96', '97-99'],
        'Atenção':         ['1', '2-6', '7-84', '85-93', '94-99'],
    },
    'Abreviado': {
        'EXPLORAÇÃO':      ['1', '2-6', '7-84', '85-96', '97-99'],
        'ESQUIVA':         ['<1', '1-6', '7-85', '86-96', '97-99'],
        'SENSIBILIDADE':   ['1', '2-7', '8-85', '86-96', '97-99'],
        'OBSERVAÇÃO':      ['1-2', '3-7', '8-86', '87-95', '96-99'],
        'Sensorial':       ['1-2', '3-8', '9-83', '84-96', '97-99'],
        'Comportamental':  ['1-2', '3-7', '8-84', '85-96', '97-99'],
    },
    'Professor': {
        'EXPLORAÇÃO':      ['<1', '1-5', '6-86', '87-94', '95-99'],
        'ESQUIVA':         ['1-2', '3-6', '7-88', '89-96', '97-99'],
        'SENSIBILIDADE':   ['<1', '1-5', '6-86', '87-95', '96-99'],
        'OBSERVAÇÃO':      ['<1', '1-4', '5-85', '86-95', '96-99'],
        'Auditivo':        ['<1', '1-3', '4-88', '89-95', '96-99'],
        'Visual':          ['', '1-3', '4-84', '85-94', '95-99'],
        'Tato':            ['1', '2-5', '6-87', '88-95', '96-99'],
        'Movimentos':      ['<1', '1-4', '5-86', '87-95', '96-99'],
        'Comportamental':  ['<1', '1-5', '6-80', '81-93', '94-99'],
        'Fator 1':         ['<1', '1-4', '5-87', '88-95', '96-99'],
        'Fator 2':         ['<1', '1-5', '6-87', '88-95', '96-99'],
        'Fator 3':         ['1-2', '3-5', '6-87', '88-96', '97-99'],
        'Fator 4':         ['1-2', '3-5', '6-87', '88-96', '97-99'],
    },
}

# ───────────────────────────────── lógica ────────────────────────────────────
_ABBREV = {'MUITO MENOS': 0, 'MENOS': 1, 'COMO A MAIORIA': 2, 'MAIS': 3, 'MUITO MAIS': 4}


def _key(s) -> str:
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return ' '.join(s.upper().split())


_CUTOFFS_N = {_key(f): {_key(k): v for k, v in scales.items()} for f, scales in CUTOFFS.items()}
_PERCENTIS_N = {_key(f): {_key(k): v for k, v in scales.items()} for f, scales in PERCENTIS.items()}


def form_key(sheet_name: str) -> str:
    """'Perfil Sensorial 2 - Criança' -> 'CRIANCA'."""
    tail = str(sheet_name).split(' - ', 1)[-1]
    return _key(tail)


def classify(sheet_name: str, scale: str, raw):
    """→ (banda, faixa_percentil) ou (None, None) se não houver norma/valor."""
    if raw in (None, '') or not isinstance(raw, (int, float)):
        return None, None
    fk, sk = form_key(sheet_name), _key(scale)
    cuts = _CUTOFFS_N.get(fk, {}).get(sk)
    pcts = _PERCENTIS_N.get(fk, {}).get(sk)
    band = None
    if cuts:
        band = len(BANDS) - 1
        for i, lim in enumerate(cuts):
            if lim is not None and raw <= lim:
                band = i
                break
    if band is None:
        return None, None
    pct = pcts[band] if pcts and band < len(pcts) else ''
    return BANDS[band], pct


def annotate_tables(sheet_name: str, tables: list[dict]) -> None:
    """Acrescenta 'Classificação' e 'Percentil (norma)' às tabelas de resultado.

    Remove as colunas 'Percentil'/'Status' que vinham da planilha (a de percentil
    ficava vazia; a de status usava cortes errados)."""
    for t in tables:
        cols = t['columns']
        labels = [str(c.get('label', '')).lower() for c in cols]
        try:
            bruta_ix = next(i for i, l in enumerate(labels) if 'brut' in l)
        except StopIteration:
            continue
        drop = {i for i, l in enumerate(labels) if l in ('percentil', 'status') or 'percentil' in l}
        keep = [i for i in range(len(cols)) if i not in drop]

        new_cols = [cols[i] for i in keep] + [
            {'col': None, 'label': 'Classificação'},
            {'col': None, 'label': 'Percentil (norma)'},
        ]
        for row in t['rows']:
            vals = row['values']
            scale = vals[0] if vals else ''
            raw = vals[bruta_ix] if bruta_ix < len(vals) else None
            band, pct = classify(sheet_name, scale, raw)
            row['values'] = [vals[i] if i < len(vals) else '' for i in keep] + [band or '', pct or '']
            if 'cells' in row:
                row['cells'] = [row['cells'][i] for i in keep if i < len(row['cells'])] + [None, None]
        t['columns'] = new_cols


def _missing():
    out = []
    for form, scales in CUTOFFS.items():
        faltam = [k for k, v in scales.items() if not v]
        if faltam:
            out.append(f'{form}: {", ".join(faltam)}')
    return out


if __name__ == '__main__':
    m = _missing()
    if m:
        print('Faltam faixas de corte (digite em CUTOFFS):')
        for line in m:
            print('  -', line)
    else:
        print('Todas as faixas de corte preenchidas.')
