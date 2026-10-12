"""Folha de respostas do RAVLT, igual à ficha em papel.

A planilha de correção do RAVLT (aba "RAVLT") já é a própria ficha: a ordem em
que cada palavra foi evocada em cada tentativa, as intrusões e o reconhecimento
(S/N). Este módulo só descreve esse layout — com as palavras lidas da própria
planilha — e libera essas células como entrada. Quem conta e corrige continua
sendo a planilha (COUNT, COUNTIF, efeito de primazia/recência, reconhecimento).
"""
from __future__ import annotations

SHEET = 'RAVLT'
ROWS = range(11, 26)                      # 15 palavras
LIST_A_COLS = ['C', 'D', 'E', 'F', 'G']  # A1..A5 (palavras da coluna B)
LIST_B_COL = 'I'                          # B1 (palavras da coluna H)
LATE_A_COLS = ['J', 'K']                  # A6, A7 (palavras da coluna L = lista A)
INTRUSION_ROWS = range(30, 40)            # até 10 intrusões por tentativa
INTRUSION_COLS = ['C', 'D', 'E', 'F', 'G', 'I', 'J', 'K']
TRIALS = ['A1', 'A2', 'A3', 'A4', 'A5', 'B1', 'A6', 'A7']
RECOG_ROWS = range(45, 55)
RECOG_PAIRS = [('C', 'D'), ('E', 'F'), ('G', 'H'), ('I', 'J'), ('K', 'L')]  # (célula S/N, palavra)


def _col_num(col: str) -> int:
    return ord(col) - 64


def layout(rows: dict) -> dict:
    """rows = WorkbookEngine._sheet_rows('RAVLT'). Devolve a ficha para a tela."""
    def text(col: str, row: int) -> str:
        v = rows.get(row, {}).get(_col_num(col), {}).get('value')
        return '' if v is None else str(v).strip()

    trials = [{'trial': t, 'cells': []} for t in TRIALS]
    for r in ROWS:
        for i, c in enumerate(LIST_A_COLS):
            trials[i]['cells'].append({'cell': f'{c}{r}', 'word': text('B', r)})
        trials[5]['cells'].append({'cell': f'{LIST_B_COL}{r}', 'word': text('H', r)})
        for i, c in enumerate(LATE_A_COLS):
            trials[6 + i]['cells'].append({'cell': f'{c}{r}', 'word': text('L', r)})
    intrusions = {t: [f'{c}{r}' for r in INTRUSION_ROWS] for t, c in zip(TRIALS, INTRUSION_COLS)}
    recognition = [{'cell': f'{sn}{r}', 'word': text(w, r)}
                   for sn, w in RECOG_PAIRS for r in RECOG_ROWS if text(w, r)]
    return {
        'list_a': [text('B', r) for r in ROWS],
        'list_b': [text('H', r) for r in ROWS],
        'trials': trials,
        'intrusions': intrusions,
        'recognition': recognition,
    }


def input_cells(sheet: dict) -> set[str]:
    cells = {c['cell'] for t in sheet['trials'] for c in t['cells']}
    cells |= {c for cs in sheet['intrusions'].values() for c in cs}
    cells |= {r['cell'] for r in sheet['recognition']}
    return cells
