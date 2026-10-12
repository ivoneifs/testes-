"""Vineland-3 (Formulários Extensivos): entrada item a item SÓ pelo número do item.

O texto das perguntas é da Pearson e NÃO entra no app: o profissional lê o próprio
protocolo impresso e marca 2 / 1 / 0 (e "Est") por número. Aqui fica apenas a
estrutura do formulário (quantos itens cada subdomínio tem e o item inicial por
idade) e onde a planilha de correção recebe o ponto bruto de cada subdomínio.

Quem corrige continua sendo a planilha (abas Vin_3_Ext_Ent / Vin_3_Ext_Pais):
v-escala, idade equivalente, escala de crescimento, domínios, CCA e mal-adaptativo.
A tela soma os itens com as regras de basal/teto e grava o bruto nas células H.
As respostas de cada item vão junto (chaves `vin:<sub>:<n>`) só para reabrir em
Testes realizados — a planilha não as recebe.
"""
from __future__ import annotations

ITEM_PREFIX = 'vin:'

# (chave, nome, domínio, célula do bruto, nº de itens, idade mínima em anos)
SUBDOMINIOS = [
    ('rec', 'Receptiva', 'Comunicação', 'H19', 39, 0),
    ('exp', 'Expressiva', 'Comunicação', 'H22', 49, 0),
    ('esc', 'Escrita', 'Comunicação', 'H25', 38, 3),
    ('pes', 'Pessoal', 'Atividades da Vida Diária', 'H29', 55, 0),
    ('dom', 'Doméstico', 'Atividades da Vida Diária', 'H32', 30, 3),
    ('cmd', 'Comunidade', 'Atividades da Vida Diária', 'H35', 58, 3),
    ('rin', 'Relacionamentos Interpessoais', 'Socialização', 'H39', 43, 0),
    ('bri', 'Brincar e Lazer', 'Socialização', 'H42', 36, 0),
    ('enf', 'Habilidades de Enfrentamento', 'Socialização', 'H45', 33, 2),
    ('cmg', 'Coordenação Motora Grossa', 'Habilidades Motoras', 'H49', 43, 0),
    ('cmf', 'Coordenação Motora Fina', 'Habilidades Motoras', 'H50', 34, 0),
]

# Item inicial por idade (anos completos) — as setas do protocolo. [(idade mínima, item)]
INICIO = {
    'entrevista': {
        'rec': [(0, 1), (1, 18), (2, 27), (3, 33)],
        'exp': [(0, 1), (1, 12), (2, 29), (3, 43)],
        'esc': [(0, 1), (3, 6), (4, 9), (5, 14), (6, 25), (8, 30)],
        'pes': [(0, 1), (1, 9), (2, 25), (3, 33), (4, 45)],
        'dom': [(0, 1), (3, 5), (5, 10), (7, 18), (9, 25)],
        'cmd': [(0, 1), (3, 10), (5, 13), (6, 25), (8, 33), (10, 38), (12, 44)],
        'rin': [(0, 1), (1, 14), (2, 23), (3, 31), (4, 36), (5, 40)],
        'bri': [(0, 1), (1, 7), (2, 19), (3, 22), (4, 28)],
        'enf': [(0, 1), (1, 6), (2, 14), (3, 17), (4, 22), (6, 28)],
        'cmg': [(0, 1), (1, 20), (2, 33), (3, 38)],
        'cmf': [(0, 1), (1, 10), (2, 14), (3, 20), (4, 26), (5, 30)],
    },
    'pais': {
        'rec': [(0, 1), (3, 11), (6, 15), (8, 19)],
        'exp': [(0, 1), (3, 11), (6, 26), (8, 30)],
        'esc': [(0, 1), (7, 7), (9, 15)],
        'pes': [(0, 1), (4, 10), (7, 26), (9, 34)],
        'dom': [(0, 1)],
        'cmd': [(0, 1), (9, 10), (12, 17)],
        'rin': [(0, 1), (10, 7)],
        'bri': [(0, 1)],
        'enf': [(0, 1)],
        'cmg': [(0, 1), (2, 8), (4, 15), (6, 27)],
        'cmf': [(0, 1), (4, 5), (7, 15)],
    },
}

# Comportamento mal-adaptativo (a partir de 3 anos): todos os itens, sem basal/teto.
MAL = [
    ('int', 'Internalizante (Seção A)', 'H109', 13),
    ('ext', 'Externalizante (Seção B)', 'H113', 11),
]
# Itens críticos 1–20: a planilha recebe 1 ou 2 (0 = em branco) nestas células.
CRITICOS = ['M109', 'O109', 'Q109', 'M110', 'O110', 'Q110', 'M111', 'O111', 'Q111', 'M112',
            'M113', 'O113', 'Q113', 'M114', 'O114', 'Q114', 'M115', 'O115', 'Q115', 'M116']

FORMS = {
    'Vin_3_Ext_Ent': ('entrevista', 'Formulário de Entrevista Extensivo'),
    'Vin_3_Ext_Pais': ('pais', 'Formulário Compreensivo de Pais/Cuidadores'),
}
# Nível do intervalo de confiança: sem ele a planilha não calcula domínios nem CCA.
CONF_CELL = 'L54'
RESPONDENTE_CELL = 'R3'


def is_form(sheet: str) -> bool:
    return sheet in FORMS


def layout(sheet: str) -> dict:
    forma, titulo = FORMS[sheet]
    return {
        'forma': forma, 'titulo': titulo,
        'regra': ('Basal: 4 itens seguidos com 2 (os anteriores valem 2). '
                  'Teto: 4 itens seguidos com 0 (os seguintes valem 0).'),
        'subdominios': [{'key': k, 'nome': n, 'dominio': d, 'cell': c, 'itens': q, 'idade_min': a,
                         'inicio': INICIO[forma][k]} for k, n, d, c, q, a in SUBDOMINIOS],
        'mal_adaptativo': [{'key': k, 'nome': n, 'cell': c, 'itens': q} for k, n, c, q in MAL],
        'criticos': CRITICOS,
    }


def raw_fields() -> list[dict]:
    out = [{'cell': c, 'label': f'{n} — pontos brutos', 'current': '', 'source': 'vineland',
            'allow_override_formula': False, 'group': d, 'range': [0, 2 * q]}
           for _k, n, d, c, q, _a in SUBDOMINIOS]
    out += [{'cell': c, 'label': f'{n} — pontos brutos', 'current': '', 'source': 'vineland',
             'allow_override_formula': False, 'group': 'Comportamento mal-adaptativo', 'range': [0, 2 * q]}
            for _k, n, c, q in MAL]
    return out


def parameters(sheet: str) -> list[dict]:
    return [
        {'cell': RESPONDENTE_CELL, 'label': 'Respondente (ex.: mãe, pai, avó)', 'current': ''},
        {'cell': CONF_CELL, 'label': 'Intervalo de confiança (%)', 'current': '95',
         'options': ['85', '90', '95'], 'selector': True},
    ]


def split_inputs(raw_scores: dict) -> dict:
    """Tira as respostas por item (só servem para reabrir a tela)."""
    return {k: v for k, v in (raw_scores or {}).items() if not str(k).startswith(ITEM_PREFIX)}


def coerce_params(parameters: dict) -> dict:
    p = dict(parameters or {})
    v = p.get(CONF_CELL)
    if v not in (None, ''):
        try:
            p[CONF_CELL] = float(str(v).replace(',', '.'))
        except ValueError:
            pass
    else:
        p[CONF_CELL] = 95.0
    return p
