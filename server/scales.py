"""Escalas por questionário (não são planilhas de correção).

Instrumentos de rastreamento com pontuação publicada e simples (soma de itens +
nota de corte) — o profissional já faz essa conta à mão; aqui é só automatizado,
igual aos instrumentos de planilha. Nada de norma proprietária: a EFA entra só com
as somas brutas por domínio (a classificação depende das tabelas normativas do
manual, que não temos) — o resultado diz isso explicitamente.

Cada escala expõe `meta()` e `score()` no MESMO formato do WorkbookEngine, para
o front e o /api/score não precisarem saber a diferença.
"""
from __future__ import annotations

# ─────────────────────────── definições ──────────────────────────────────────
ATA_AREAS = [
    'I. Dificuldade na interação social',
    'II. Manipulação do ambiente',
    'III. Utilização das pessoas a seu redor',
    'IV. Resistência a mudanças',
    'V. Busca de uma ordem rígida',
    'VI. Falta de contato visual / olhar indefinido',
    'VII. Mímica inexpressiva',
    'VIII. Distúrbios de sono',
    'IX. Alteração na alimentação',
    'X. Dificuldade no controle dos esfíncteres',
    'XI. Exploração dos objetos (apalpar, chupar)',
    'XII. Uso inapropriado dos objetos',
    'XIII. Falta de atenção',
    'XIV. Ausência de interesse pela aprendizagem',
    'XV. Falta de iniciativa',
    'XVI. Alteração de linguagem e comunicação',
    'XVII. Não manifesta habilidades e conhecimentos',
    'XVIII. Reações inapropriadas ante a frustração',
    'XIX. Não assume responsabilidades',
    'XX. Hiperatividade / hipoatividade',
    'XXI. Movimentos estereotipados e repetitivos',
    'XXII. Ignora o perigo',
    'XXIII. Aparecimento antes dos 36 meses',
]


def _num(v):
    if isinstance(v, (int, float)):
        return v
    try:
        return float(str(v).replace(',', '.'))
    except (TypeError, ValueError):
        return None


def _table(title, columns, rows):
    return {
        'title': title,
        'header_row': 0,
        'columns': [{'col': None, 'label': c} for c in columns],
        'rows': [{'row': i + 1, 'values': r, 'cells': [None] * len(r)} for i, r in enumerate(rows)],
    }


# ─────────────────────────── ATA ─────────────────────────────────────────────
def _ata_meta():
    fields = []
    for i, area in enumerate(ATA_AREAS, 1):
        fields.append({
            'cell': f'a{i}', 'label': area, 'current': '',
            'source': 'scale-item', 'allow_override_formula': False,
            'group': 'Áreas avaliadas (0 = não apresenta · 1 = ocasionalmente · 2 = frequentemente)',
            'range': [0, 2],
        })
    return {
        'name': 'ATA – Escala de Traços Autísticos',
        'raw_fields': fields, 'detail_fields': [], 'input_mode': 'itens',
        'profile_cells': {}, 'parameters': [], 'tables': [], 'chart_type': 'escala',
        'note': 'Rastreamento (Ballabriga et al., 1994; adapt. Assumpção et al., 1999). '
                'Não tem finalidade diagnóstica. Corte ≥ 15 = indicativo significativo de traços autísticos.',
    }


def _ata_score(patient, raw_scores):
    vals = []
    for i in range(1, len(ATA_AREAS) + 1):
        v = _num((raw_scores or {}).get(f'a{i}'))
        vals.append(int(v) if v is not None else 0)
    total = sum(vals)
    band = ('Indicativo significativo de traços autísticos — investigação clínica mais aprofundada'
            if total >= 15 else 'Abaixo da nota de corte — ausência ou baixa expressão de traços autísticos')
    result = _table('Resultado', ['Medida', 'Escore', 'Classificação'],
                    [['Escore total (0–46)', total, band]])
    areas = _table('Pontuação por área', ['Área', 'Escore (0–2)'],
                   [[ATA_AREAS[i], vals[i]] for i in range(len(ATA_AREAS))])
    applied = [{'cell': f'a{i+1}', 'label': ATA_AREAS[i], 'value': vals[i],
                'source': 'scale-item', 'allow_override_formula': False} for i in range(len(ATA_AREAS))]
    return {'test': 'ATA – Escala de Traços Autísticos', 'chart_type': 'escala',
            'raw_scores': applied, 'tables': [result, areas], 'profile_cells': {}, 'parameters': []}


# ─────────────────────────── HADS ────────────────────────────────────────────
def _hads_band(score):
    if score is None:
        return ''
    if score <= 7:
        return 'Normal (sem indício clínico)'
    if score <= 10:
        return 'Leve / limítrofe'
    return 'Clinicamente significativo'


def _hads_meta():
    fields = [
        {'cell': 'hads_a', 'label': 'HADS-A · Ansiedade — total dos 7 itens', 'current': '',
         'source': 'scale-item', 'allow_override_formula': False,
         'group': 'Somas das subescalas (cada item 0–3; total 0–21)', 'range': [0, 21]},
        {'cell': 'hads_d', 'label': 'HADS-D · Depressão — total dos 7 itens', 'current': '',
         'source': 'scale-item', 'allow_override_formula': False,
         'group': 'Somas das subescalas (cada item 0–3; total 0–21)', 'range': [0, 21]},
    ]
    return {
        'name': 'HADS – Ansiedade e Depressão',
        'raw_fields': fields, 'detail_fields': [], 'input_mode': 'itens',
        'profile_cells': {}, 'parameters': [], 'tables': [], 'chart_type': 'escala',
        'note': 'Hospital Anxiety and Depression Scale. 14 itens (7 + 7), 0–3 cada. '
                'Corte: 0–7 normal · 8–10 leve · ≥ 11 significativo.',
    }


def _hads_score(patient, raw_scores):
    a = _num((raw_scores or {}).get('hads_a'))
    d = _num((raw_scores or {}).get('hads_d'))
    ai = int(a) if a is not None else None
    di = int(d) if d is not None else None
    rows = [
        ['Ansiedade (HADS-A)', ai if ai is not None else '', _hads_band(ai)],
        ['Depressão (HADS-D)', di if di is not None else '', _hads_band(di)],
    ]
    applied = [
        {'cell': 'hads_a', 'label': 'HADS-A · Ansiedade', 'value': ai if ai is not None else '',
         'source': 'scale-item', 'allow_override_formula': False},
        {'cell': 'hads_d', 'label': 'HADS-D · Depressão', 'value': di if di is not None else '',
         'source': 'scale-item', 'allow_override_formula': False},
    ]
    return {'test': 'HADS – Ansiedade e Depressão', 'chart_type': 'escala',
            'raw_scores': applied,
            'tables': [_table('Resultado', ['Subescala', 'Escore (0–21)', 'Classificação'], rows)],
            'profile_cells': {}, 'parameters': []}


# ─────────────────────────── EFA ─────────────────────────────────────────────
# Avaliação de Funcionamento Adaptativo. Cada item: 2 = sim · 1 = com ajuda ·
# 0 = não · em branco = "não sei" (não pontua). Somas brutas por domínio.
EFA_DOMINIOS = [
    ('soc', 'Social', [
        'Entende o que as pessoas falam', 'Participa de atividades de interesse', 'Entende gestos',
        'Faz favores simples', 'Tem melhores amigos', 'Sabe se comportar socialmente',
        'É compreendido por estranhos', 'Entende expressões figuradas', 'Oferece ajuda',
        'Convida pares para atividades', 'Segue regras da família', 'Interação (espera a vez)',
        'Interessa-se pelo que outros pensam', 'Controle inibitório (não grita/bate)', 'Percebe más intenções']),
    ('pra', 'Prático', [
        'Assoa e limpa o nariz', 'Coloca lixo no cesto', 'Sabe tomar banho', 'Escova os dentes',
        'Veste/tira roupas', 'Usa aparelhos elétricos', 'Usa vaso sanitário', 'Lava o cabelo',
        'Calça sapatos/cadarços', 'Guarda objetos', 'Perigo com estranhos', 'Escolhe roupa/clima',
        'Evita perigos (rua/quente)', 'Pequenas tarefas domésticas', 'Usa faca (manteiga)',
        'Prepara alimentos simples', 'Compra algo sozinho', 'Come com garfo e faca',
        'Organiza rotina', 'Serve a própria comida', 'Corta carnes', 'Cuida de ferimentos leves',
        'Estratégias para objetivos', 'Sabe telefone de familiares']),
    ('con', 'Conceitual', [
        'Faz dever de casa', 'Noção de tempo/horários', 'Entende regras de jogos',
        'Placas e símbolos', 'Sabe dia da semana', 'Soma e subtração', 'Habilidades de escrita',
        'Habilidades de leitura', 'Valor de moedas', 'Letra cursiva', 'Multiplicação e divisão']),
]
EFA_NAME = 'EFA – Avaliação de Funcionamento Adaptativo'


def _efa_meta():
    fields = []
    for pre, dom, itens in EFA_DOMINIOS:
        for i, item in enumerate(itens, 1):
            fields.append({
                'cell': f'{pre}{i}', 'label': f'{i}. {item}', 'current': '',
                'source': 'scale-item', 'allow_override_formula': False,
                'group': f'Domínio {dom} (2 = sim · 1 = com ajuda · 0 = não · em branco = não sei)',
                'range': [0, 2],
            })
    return {
        'name': EFA_NAME,
        'raw_fields': fields, 'detail_fields': [], 'input_mode': 'itens',
        'profile_cells': {}, 'parameters': [], 'tables': [], 'chart_type': 'escala',
        'note': 'EFA: 50 itens (Social 15, Prático 24, Conceitual 11), 0–2 cada. O sistema soma os '
                'pontos brutos por domínio; a classificação normativa exige as tabelas do manual.',
    }


def _efa_score(patient, raw_scores):
    rows, applied, total, total_max, ns_total = [], [], 0, 0, 0
    por_item = []
    for pre, dom, itens in EFA_DOMINIOS:
        soma, ns = 0, 0
        for i, item in enumerate(itens, 1):
            v = _num((raw_scores or {}).get(f'{pre}{i}'))
            if v is None:
                ns += 1
                val = ''
            else:
                val = int(max(0, min(2, v)))
                soma += val
            applied.append({'cell': f'{pre}{i}', 'label': f'{i}. {item}', 'value': val,
                            'source': 'scale-item', 'allow_override_formula': False})
            por_item.append([dom, f'{i}. {item}', val if val != '' else 'Não sei'])
        mx = 2 * len(itens)
        rows.append([dom, soma, mx, f'{round(100 * soma / mx)}%', ns])
        total, total_max, ns_total = total + soma, total_max + mx, ns_total + ns
    rows.append(['Total', total, total_max, f'{round(100 * total / total_max)}%', ns_total])
    result = _table('Pontuação bruta por domínio',
                    ['Domínio', 'Pontos brutos', 'Máximo', '% do máximo', 'Itens "não sei"'], rows)
    nota = _table('Classificação normativa', ['Observação'],
                  [['Classificação normativa não aplicada: requer as tabelas do manual da EFA por '
                    'faixa etária. Os valores acima são somas brutas.']])
    itens_t = _table('Respostas por item', ['Domínio', 'Item', 'Pontos'], por_item)
    return {'test': EFA_NAME, 'chart_type': 'escala', 'raw_scores': applied,
            'tables': [result, nota, itens_t], 'profile_cells': {}, 'parameters': []}


# ─────────────────────────── registro ────────────────────────────────────────
_SCALES = {
    'ATA – Escala de Traços Autísticos': (_ata_meta, _ata_score),
    'HADS – Ansiedade e Depressão': (_hads_meta, _hads_score),
    EFA_NAME: (_efa_meta, _efa_score),
}


def is_scale(name: str) -> bool:
    return name in _SCALES


def catalog_entries():
    return [{'name': n, 'chart_type': 'escala', 'kind': 'escala'} for n in _SCALES]


def meta(name: str):
    return _SCALES[name][0]()


def score(name: str, patient: dict, raw_scores: dict, parameters: dict | None = None):
    return _SCALES[name][1](patient or {}, raw_scores or {})
