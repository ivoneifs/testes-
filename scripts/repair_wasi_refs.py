"""Conserta as 112 fórmulas com #REF! da aba WASI em data/neuro_normas.db.

Origem do defeito: a aba WASI foi copiada do WISC-IV (15 subtestes) mas a WASI
só tem 4 (VC/CB/SM/RM). Ao apagar as linhas dos subtestes que não existem,
o Excel corrompeu as referências -> #REF!.

Correções (equivalentes devem ser feitas no Planilha_correcao.xlsx):
  1. Bloco "Facilidades e Dificuldades" (AB/AC/AD 57..95): COUNTIF(#REF!,"x")
     conta subtestes inexistentes -> vira 0.
  2. AB13 "TOTAL" (idade mental): a fórmula gigante herdada do WISC referencia
     células apagadas -> passa a espelhar QIT-4 (AB11).

Rodar: python scripts/repair_wasi_refs.py   (idempotente)
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / 'data' / 'neuro_normas.db'


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    sid = con.execute("select sheet_idx from sheets where name='WASI'").fetchone()[0]

    fixed = 0

    # 1) COUNTIF(#REF!, ...) -> 0
    rows = con.execute(
        "select row_num, col_num, formula from cells "
        "where sheet_idx=? and formula like '%#REF!%' and upper(formula) like 'COUNTIF(%'",
        (sid,),
    ).fetchall()
    for r in rows:
        con.execute(
            "update cells set formula='0', value_kind='number', num_value=0, text_value=NULL "
            "where sheet_idx=? and row_num=? and col_num=?",
            (sid, r['row_num'], r['col_num']),
        )
        fixed += 1

    # 2) AB13 (col 28, row 13) -> espelha QIT-4
    r = con.execute(
        "select formula from cells where sheet_idx=? and row_num=13 and col_num=28", (sid,)
    ).fetchone()
    if r and r['formula'] and '#REF!' in r['formula']:
        con.execute(
            "update cells set formula='IF(N3=\"\",\"\",AB11)', value_kind='number', "
            "num_value=0, text_value=NULL where sheet_idx=? and row_num=13 and col_num=28",
            (sid,),
        )
        fixed += 1

    # 3) limpa valores em cache gravados como erro (#REF!/#VALUE! do estado
    #    corrompido) — o motor recalcula a fórmula; o cache só serve de fallback.
    cur = con.execute(
        "update cells set value_kind='blank', num_value=NULL, text_value=NULL "
        "where sheet_idx=? and value_kind='error' and text_value='#REF!'",
        (sid,),
    )
    fixed += cur.rowcount

    # sobra de #REF! em qualquer fórmula da aba? (diagnóstico)
    left = con.execute(
        "select count(*) from cells where sheet_idx=? and formula like '%#REF!%'", (sid,)
    ).fetchone()[0]

    con.commit()
    con.close()
    print(f'WASI: {fixed} fórmulas corrigidas; {left} ainda com #REF! (deve ser 0)')


if __name__ == '__main__':
    main()
