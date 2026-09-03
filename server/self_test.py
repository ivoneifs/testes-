from __future__ import annotations

import json
from pathlib import Path

from .workbook_engine import WorkbookEngine

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    eng = WorkbookEngine()
    tests = eng.list_tests()
    problems = []
    catalog = []
    for name in tests:
        try:
            meta = eng.test_meta(name)
            catalog.append({
                'test': name,
                'input_mode': meta.get('input_mode'),
                'raw_fields': len(meta.get('raw_fields', [])),
                'hidden_detail_fields': len(meta.get('detail_fields', [])),
                'tables': len(meta.get('tables', [])),
                'chart_type': meta.get('chart_type'),
                'profile_cells': meta.get('profile_cells', {}),
            })
            if not meta.get('raw_fields') and name not in ('WISC-Compar', 'Perfil Sensorial 2 - Consolidado'):
                problems.append(f'{name}: nenhum campo de entrada detectado')
        except Exception as exc:
            problems.append(f'{name}: {type(exc).__name__}: {exc}')

    # Smoke test 1: WISC-IV existing raw-score chain -> composite results.
    wisc_meta = eng.test_meta('WISC-IV')
    wisc_raw = {
        f['cell']: f['current']
        for f in wisc_meta['raw_fields']
        if f['cell'].startswith('E') and isinstance(f.get('current'), (int, float))
    }
    wisc = eng.score('WISC-IV', {
        'name': 'AutoTeste', 'birth_date': '2014-12-25', 'application_date': '2025-11-10',
        'sex': 'Masculino', 'education': '4º ano'
    }, wisc_raw, {})
    if not any(any('Q.I. TOTAL' == str(v) for v in row['values']) for t in wisc['tables'] for row in t['rows']):
        problems.append('WISC-IV: cadeia de índices/QI não localizada no auto-teste')

    # Smoke test 2: RAVLT point-bruto-only conversion by age.
    ravlt_meta = eng.test_meta('RAVLT')
    by_label = {f['label']: f['cell'] for f in ravlt_meta['raw_fields']}
    required = ['A1','A2','A3','A4','A5','B1','A6','A7']
    if all(k in by_label for k in required):
        vals = [6,8,10,11,12,5,10,9]
        ravlt_raw = {by_label[k]: v for k,v in zip(required, vals)}
        ravlt = eng.score('RAVLT', {
            'name': 'AutoTeste', 'birth_date': '1990-01-01', 'application_date': '2026-08-31',
            'sex': 'Feminino', 'education': 'Superior'
        }, ravlt_raw, {})
        first = ravlt['tables'][0]['rows'][0]['values'] if ravlt['tables'] and ravlt['tables'][0]['rows'] else []
        if len(first) < 2 or first[0] != 6 or first[1] in ('', None):
            problems.append('RAVLT: conversão PB→norma não passou no auto-teste')
    else:
        problems.append('RAVLT: campos A1-A7/B1 não detectados no modo PB')

    out = {'tests': len(tests), 'problems': problems, 'catalog': catalog}
    (ROOT/'data'/'catalog_diagnostic.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'tests': len(tests), 'problems': problems}, ensure_ascii=False, indent=2))
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
