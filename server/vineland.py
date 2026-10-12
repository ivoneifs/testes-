"""Vineland-3 (6 formas): entrada item a item SÓ pelo número do item.

O texto das perguntas é da Pearson e NÃO entra no app: o profissional lê o próprio
protocolo impresso e marca 2 / 1 / 0 (e "Est") por número. Aqui fica apenas a
estrutura de cada formulário (quantos itens cada subdomínio tem e o item inicial por
idade) e onde a planilha de correção recebe os pontos brutos.

Quem corrige continua sendo a planilha (abas Vin_3_*): v-escala, idade equivalente,
escala de crescimento, domínios, CCA e mal-adaptativo. A tela soma os itens com as
regras de basal/teto e grava o bruto nas células H. Seção com `itens=None` = ainda
sem a folha do protocolo: a tela pede o bruto digitado. As respostas de cada item vão
junto (chaves `vin:<sub>:<n>`) só para reabrir em Testes realizados — a planilha não
as recebe.
"""
from __future__ import annotations

ITEM_PREFIX = 'vin:'
REGRA = ('Basal: 4 itens seguidos com 2 (os anteriores valem 2). '
         'Teto: 4 itens seguidos com 0 (os seguintes valem 0).')


def _sub(key, nome, dominio, cell, itens, idade_min, inicio):
    return {'key': key, 'nome': nome, 'dominio': dominio, 'cell': cell, 'itens': itens,
            'idade_min': idade_min, 'inicio': inicio}


# Extensivos — células de bruto iguais nas três abas; nº de itens e setas de início
# conferidos nas folhas escaneadas (Entrevista, Pais/Cuidadores, Professor).
_EXT_CELLS = {'rec': 'H19', 'exp': 'H22', 'esc': 'H25', 'pes': 'H29', 'dom': 'H32', 'cmd': 'H35',
              'rin': 'H39', 'bri': 'H42', 'enf': 'H45', 'cmg': 'H49', 'cmf': 'H50'}
COM, AVD, SOC, MOT = 'Comunicação', 'Atividades da Vida Diária', 'Socialização', 'Habilidades Motoras'


def _ext(spec):
    return [_sub(k, n, d, _EXT_CELLS[k], q, a, i) for k, n, d, q, a, i in spec]


EXT_ENT = _ext([
    ('rec', 'Receptiva', COM, 39, 0, [(0, 1), (1, 18), (2, 27), (3, 33)]),
    ('exp', 'Expressiva', COM, 49, 0, [(0, 1), (1, 12), (2, 29), (3, 43)]),
    ('esc', 'Escrita', COM, 38, 3, [(0, 1), (3, 6), (4, 9), (5, 14), (6, 25), (8, 30)]),
    ('pes', 'Pessoal', AVD, 55, 0, [(0, 1), (1, 9), (2, 25), (3, 33), (4, 45)]),
    ('dom', 'Doméstico', AVD, 30, 3, [(0, 1), (3, 5), (5, 10), (7, 18), (9, 25)]),
    ('cmd', 'Comunidade', AVD, 58, 3, [(0, 1), (3, 10), (5, 13), (6, 25), (8, 33), (10, 38), (12, 44)]),
    ('rin', 'Relacionamentos Interpessoais', SOC, 43, 0, [(0, 1), (1, 14), (2, 23), (3, 31), (4, 36), (5, 40)]),
    ('bri', 'Brincar e Lazer', SOC, 36, 0, [(0, 1), (1, 7), (2, 19), (3, 22), (4, 28)]),
    ('enf', 'Habilidades de Enfrentamento', SOC, 33, 2, [(0, 1), (1, 6), (2, 14), (3, 17), (4, 22), (6, 28)]),
    ('cmg', 'Coordenação Motora Grossa', MOT, 43, 0, [(0, 1), (1, 20), (2, 33), (3, 38)]),
    ('cmf', 'Coordenação Motora Fina', MOT, 34, 0, [(0, 1), (1, 10), (2, 14), (3, 20), (4, 26), (5, 30)]),
])
EXT_PAIS = _ext([
    ('rec', 'Receptiva (Ouvir e Entender)', COM, 39, 0, [(0, 1), (3, 11), (6, 15), (8, 19)]),
    ('exp', 'Expressiva (Falar)', COM, 49, 0, [(0, 1), (3, 11), (6, 26), (8, 30)]),
    ('esc', 'Escrita (Leitura e Escrita)', COM, 38, 3, [(0, 1), (7, 7), (9, 15)]),
    ('pes', 'Pessoal (Cuidando de si)', AVD, 55, 0, [(0, 1), (4, 10), (7, 26), (9, 34)]),
    ('dom', 'Doméstico (Cuidando da casa)', AVD, 30, 3, [(0, 1)]),
    ('cmd', 'Comunidade (Viver em comunidade)', AVD, 58, 3, [(0, 1), (9, 10), (12, 17)]),
    ('rin', 'Relacionamentos Interpessoais', SOC, 43, 0, [(0, 1), (10, 7)]),
    ('bri', 'Brincar e Lazer', SOC, 36, 0, [(0, 1)]),
    ('enf', 'Habilidades de Enfrentamento (Adaptar)', SOC, 33, 2, [(0, 1)]),
    ('cmg', 'Coordenação Motora Grossa', MOT, 43, 0, [(0, 1), (2, 8), (4, 15), (6, 27)]),
    ('cmf', 'Coordenação Motora Fina', MOT, 34, 0, [(0, 1), (4, 5), (7, 15)]),
])
EXT_PROF = _ext([
    ('rec', 'Receptiva', COM, 30, 0, [(0, 1), (6, 8), (10, 14)]),
    ('exp', 'Expressiva', COM, 36, 0, [(0, 1), (6, 7), (8, 16), (10, 24)]),
    ('esc', 'Escrita', COM, 36, 0, [(0, 1), (8, 9), (10, 14)]),
    ('pes', 'Pessoal', AVD, 24, 0, [(0, 1), (8, 15)]),
    ('dom', 'Numérico', AVD, 23, 0, [(0, 1), (10, 7), (13, 13)]),
    ('cmd', 'Comunidade Escolar', AVD, 22, 0, [(0, 1)]),
    ('rin', 'Relacionamentos Interpessoais', SOC, 31, 0, [(0, 1), (12, 10)]),
    ('bri', 'Brincar e Lazer', SOC, 19, 0, [(0, 1)]),
    ('enf', 'Habilidades de Enfrentamento', SOC, 25, 0, [(0, 1)]),
    ('cmg', 'Coordenação Motora Grossa', MOT, 21, 0, [(0, 1), (6, 11)]),
    ('cmf', 'Coordenação Motora Fina', MOT, 26, 0, [(0, 1), (6, 9)]),
])

# Nível de Domínio: a planilha recebe o bruto por DOMÍNIO. Sem as folhas desses
# protocolos (nº de itens/início), por enquanto o bruto é digitado.
DOM = [_sub(k, n, n, c, None, 0, []) for k, n, c in
       [('com', COM, 'H20'), ('avd', AVD, 'H23'), ('soc', SOC, 'H26'), ('mot', MOT, 'H33')]]


def _mal(cells_counts):
    return [{'key': k, 'nome': n, 'cell': c, 'itens': q} for k, n, c, q in cells_counts]


# Críticos: a planilha recebe 1 ou 2 (0 = em branco). Layout em linhas de 3 (extensivos).
_CRIT_EXT_20 = ['M109', 'O109', 'Q109', 'M110', 'O110', 'Q110', 'M111', 'O111', 'Q111', 'M112',
                'M113', 'O113', 'Q113', 'M114', 'O114', 'Q114', 'M115', 'O115', 'Q115', 'M116']
_CRIT_EXT_17 = _CRIT_EXT_20[:17]
# Nível de Domínio: colunas de 4 (1–4 em M, 5–8 em O, 9–11 em Q), linhas 46–49.
_CRIT_DOM_11 = [f'{"MOQ"[(k - 1) // 4]}{46 + (k - 1) % 4}' for k in range(1, 12)]

FORMS = {
    'Vin_3_Ext_Ent': {'forma': 'entrevista', 'titulo': 'Formulário de Entrevista Extensivo',
                      'subdominios': EXT_ENT, 'conf': 'L54', 'criticos': _CRIT_EXT_20,
                      'mal': _mal([('int', 'Internalizante (Seção A)', 'H109', 13),
                                   ('ext', 'Externalizante (Seção B)', 'H113', 11)])},
    'Vin_3_Dom_Ent': {'forma': 'entrevista_dominio', 'titulo': 'Formulário de Entrevista de Nível de Domínio',
                      'subdominios': DOM, 'conf': 'L19', 'criticos': _CRIT_DOM_11,
                      'mal': _mal([('int', 'Internalizante (Seção A)', 'H46', None),
                                   ('ext', 'Externalizante (Seção B)', 'H48', None)])},
    'Vin_3_Ext_Pais': {'forma': 'pais', 'titulo': 'Formulário de Pais/Cuidadores Extensivo',
                       'subdominios': EXT_PAIS, 'conf': 'L54', 'criticos': _CRIT_EXT_20,
                       'mal': _mal([('int', 'Internalizante (Seção A)', 'H109', 13),
                                    ('ext', 'Externalizante (Seção B)', 'H113', 11)])},
    'Vin_3_Dom_Pais': {'forma': 'pais_dominio', 'titulo': 'Formulário de Pais/Cuidadores de Nível de Domínio',
                       'subdominios': DOM, 'conf': 'L19', 'criticos': _CRIT_DOM_11,
                       'mal': _mal([('int', 'Internalizante (Seção A)', 'H46', None),
                                    ('ext', 'Externalizante (Seção B)', 'H48', None)])},
    'Vin_3_Ext_Prof': {'forma': 'professor', 'titulo': 'Formulário de Professores Extensivo',
                       'subdominios': EXT_PROF, 'conf': 'L54', 'criticos': _CRIT_EXT_17,
                       'mal': _mal([('int', 'Internalizante (Seção A)', 'H109', None),
                                    ('ext', 'Externalizante (Seção B)', 'H113', None)])},
    'Vin_3_Dom_Prof': {'forma': 'professor_dominio', 'titulo': 'Formulário de Professores de Nível de Domínio',
                       'subdominios': DOM, 'conf': 'L19', 'criticos': _CRIT_DOM_11,
                       'mal': _mal([('int', 'Internalizante (Seção A)', 'H46', None),
                                    ('ext', 'Externalizante (Seção B)', 'H48', None)])},
}
RESPONDENTE_CELL = 'R3'


def display_name(sheet: str) -> str:
    """Nome legível (para o laudo): "Vineland-3 — Formulário …"; outros testes ficam iguais."""
    return f"Vineland-3 — {FORMS[sheet]['titulo']}" if sheet in FORMS else sheet


def is_form(sheet: str) -> bool:
    return sheet in FORMS


def layout(sheet: str) -> dict:
    f = FORMS[sheet]
    return {'forma': f['forma'], 'titulo': f['titulo'], 'regra': REGRA,
            'subdominios': f['subdominios'], 'mal_adaptativo': f['mal'], 'criticos': f['criticos']}


def raw_fields(sheet: str) -> list[dict]:
    f = FORMS[sheet]
    out = []
    for s in f['subdominios']:
        out.append({'cell': s['cell'], 'label': f"{s['nome']} — pontos brutos", 'current': '', 'source': 'vineland',
                    'allow_override_formula': False, 'group': s['dominio'],
                    'range': [0, 2 * s['itens']] if s['itens'] else None})
    for m in f['mal']:
        out.append({'cell': m['cell'], 'label': f"{m['nome']} — pontos brutos", 'current': '', 'source': 'vineland',
                    'allow_override_formula': False, 'group': 'Comportamento mal-adaptativo',
                    'range': [0, 2 * m['itens']] if m['itens'] else None})
    return out


def parameters(sheet: str) -> list[dict]:
    return [
        {'cell': RESPONDENTE_CELL, 'label': 'Respondente (ex.: mãe, pai, professora)', 'current': ''},
        {'cell': FORMS[sheet]['conf'], 'label': 'Intervalo de confiança (%)', 'current': '95',
         'options': ['85', '90', '95'], 'selector': True},
    ]


def split_inputs(raw_scores: dict) -> dict:
    """Tira as respostas por item (só servem para reabrir a tela)."""
    return {k: v for k, v in (raw_scores or {}).items() if not str(k).startswith(ITEM_PREFIX)}


def coerce_params(sheet: str, parameters: dict) -> dict:
    """Nível de confiança numérico (a planilha compara com 85/90/95); sem ele = 95."""
    conf = FORMS[sheet]['conf']
    p = dict(parameters or {})
    v = p.get(conf)
    try:
        p[conf] = float(str(v).replace(',', '.')) if v not in (None, '') else 95.0
    except ValueError:
        p[conf] = 95.0
    return p
