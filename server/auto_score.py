"""Correção automática dos testes enviados na aba "Geração de Laudo".

1. IA faz a triagem: que instrumentos há nos arquivos e se já vêm corrigidos.
2. Para os que vêm só com escores brutos e existem no catálogo do NeuroScore,
   a IA transcreve os brutos para os campos de entrada do motor.
3. O motor (planilhas + normas) corrige — igual à aba Laudos.

A IA nunca calcula norma: quem pontua é o motor. Instrumento fora do catálogo e
sem correção vira alerta para a profissional.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from . import scales
from .openai_service import extract_raw_scores, triage_instruments

_NUM = re.compile(r'^-?\d+(?:[.,]\d+)?$')


def _value(v: str):
    v = (v or '').strip()
    if _NUM.match(v):
        n = float(v.replace(',', '.'))
        return int(n) if n.is_integer() else n
    return v


def _compact(tables: list[dict]) -> list[dict]:
    """Tabelas do motor → {titulo, colunas, linhas}, sem colunas vazias (como a aba Laudos)."""
    out = []
    for t in tables or []:
        cols = [c.get('label', '') if isinstance(c, dict) else str(c) for c in t.get('columns', [])]
        rows = [r.get('values', []) for r in t.get('rows', [])]
        keep = [i for i in range(len(cols)) if any(i < len(r) and r[i] not in ('', None) for r in rows)]
        if not keep:
            continue
        out.append({'titulo': t.get('title') or '',
                    'colunas': [cols[i] for i in keep],
                    'linhas': [['' if i >= len(r) or r[i] is None else str(r[i]) for i in keep] for r in rows]})
    return out


def run(engine, file_groups: list[tuple[str, list[dict]]], patient: dict):
    """file_groups = [(nome_do_arquivo, itens_de_conteúdo)]. patient = {name, birth_date,
    application_date (ISO), sex, education}. Devolve (resultados_calculados, triagem, alertas)."""
    catalog = [t['name'] for t in engine.catalog()] + [t['name'] for t in scales.catalog_entries()]
    all_items = [it for _, items in file_groups for it in items]
    triagem = triage_instruments(all_items, catalog).get('instrumentos', [])
    alertas: list[str] = []

    todo = []
    for ins in triagem:
        nome, cat, sit = ins.get('instrumento', ''), ins.get('teste_catalogo', ''), ins.get('situacao')
        if sit == 'escores_brutos' and cat in catalog:
            todo.append(ins)
        elif sit == 'escores_brutos':
            alertas.append(f'{nome}: veio só com escores brutos e não está entre os instrumentos que o '
                           'NeuroScore corrige — envie a folha já corrigida.')
        elif sit == 'protocolo_sem_escores':
            alertas.append(f'{nome}: protocolo sem pontuação — pontue e envie os escores.')

    if todo and not (patient.get('birth_date') and patient.get('application_date')):
        alertas.append('Informe a data de nascimento e a data de aplicação para o sistema corrigir os '
                       'escores brutos pelas normas de idade.')
        return [], triagem, alertas

    def one(ins):
        test = ins['teste_catalogo']
        meta = scales.meta(test) if scales.is_scale(test) else engine.test_meta(test)
        fields = meta.get('raw_fields', [])
        wanted = set(ins.get('arquivos') or [])
        items = [it for fname, its in file_groups if fname in wanted for it in its] or all_items
        ext = extract_raw_scores(test, fields, items)
        valid = {f['cell'] for f in fields}
        raw = {v['campo']: _value(v['valor']) for v in ext.get('valores', [])
               if v.get('campo') in valid and str(v.get('valor', '')).strip() != ''}
        notes = [f'{test}: {a}' for a in ext.get('alertas', [])]
        if not raw:
            return None, notes + [f'{test}: não foi possível ler os escores brutos do documento.']
        res = (scales.score(test, patient, raw, {}) if scales.is_scale(test)
               else engine.score(test, patient, raw, {}))
        return {'teste': test, 'instrumento_no_documento': ins.get('instrumento', ''),
                'escores_brutos_usados': {f['label']: raw[f['cell']] for f in fields if f['cell'] in raw},
                'tabelas_corrigidas': _compact(res.get('tables'))}, notes

    resultados = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for ins, fut in [(i, pool.submit(one, i)) for i in todo]:
            try:
                r, notes = fut.result()
            except Exception as exc:  # um teste com problema não derruba o laudo
                r, notes = None, [f"{ins['teste_catalogo']}: falha na correção automática ({type(exc).__name__})."]
            alertas.extend(notes)
            if r:
                resultados.append(r)
    return resultados, triagem, alertas
