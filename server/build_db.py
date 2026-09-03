from __future__ import annotations

import re
import sqlite3
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
XLSX = DATA / 'Planilha_correcao.xlsx'
DB = DATA / 'neuro_normas.db'

# Workbooks extras (fora do Planilha_correcao.xlsx) ingeridos como abas adicionais.
# As abas são renomeadas para não colidir e para aparecerem com um nome claro no
# catálogo; as referências entre abas dentro do próprio workbook são reescritas
# para os nomes novos.
EXTRA_WORKBOOKS = [
    {
        'file': 'Perfil Sensorial 2-0 correcao excel.xlsx',
        'rename': {
            'BEBÊ': 'Perfil Sensorial 2 - Bebê',
            'CRI PEQUENA': 'Perfil Sensorial 2 - Criança Pequena',
            'CRIANÇA': 'Perfil Sensorial 2 - Criança',
            'PROFESSOR': 'Perfil Sensorial 2 - Professor',
            'ABREVIADO': 'Perfil Sensorial 2 - Abreviado',
            'CONSOLIDADO': 'Perfil Sensorial 2 - Consolidado',
        },
    },
]

MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG_REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
N = '{%s}' % MAIN

CELL_RE = re.compile(r'^(\$?)([A-Z]{1,3})(\$?)(\d+)$')
REF_RE = re.compile(r'(?<![A-Z0-9_])(?P<colabs>\$?)(?P<col>[A-Z]{1,3})(?P<rowabs>\$?)(?P<row>\d+)')


def col_to_num(col: str) -> int:
    n = 0
    for ch in col.upper():
        n = n * 26 + ord(ch) - 64
    return n


def num_to_col(n: int) -> str:
    out = []
    while n:
        n, r = divmod(n - 1, 26)
        out.append(chr(65 + r))
    return ''.join(reversed(out))


def split_addr(addr: str):
    m = CELL_RE.match(addr)
    if not m:
        raise ValueError(addr)
    return col_to_num(m.group(2)), int(m.group(4))


def translate_formula(formula: str, base_addr: str, target_addr: str) -> str:
    """Translate relative A1 refs in a shared Excel formula."""
    if not formula or base_addr == target_addr:
        return formula or ''
    bc, br = split_addr(base_addr)
    tc, tr = split_addr(target_addr)
    dc, dr = tc - bc, tr - br

    # Do not alter cell-like text inside quoted Excel strings.
    parts = re.split(r'("(?:[^"]|"")*")', formula)
    for i in range(0, len(parts), 2):
        segment = parts[i]
        def repl(m: re.Match):
            c_abs = m.group('colabs') == '$'
            r_abs = m.group('rowabs') == '$'
            c = col_to_num(m.group('col'))
            r = int(m.group('row'))
            if not c_abs:
                c += dc
            if not r_abs:
                r += dr
            if c < 1 or r < 1:
                return '#REF!'
            return ('$' if c_abs else '') + num_to_col(c) + ('$' if r_abs else '') + str(r)
        parts[i] = REF_RE.sub(repl, segment)
    return ''.join(parts)


def make_sheet_ref_rewriter(rename_map: dict | None):
    """Rewrite `Sheet!` / `'Sheet Name'!` prefixes in formulas to renamed sheets.

    Used only for the extra workbooks whose sheets are renamed on ingest; the main
    workbook passes ``None`` and formulas are left untouched (identity)."""
    if not rename_map:
        return lambda f: f
    pairs = sorted(rename_map.items(), key=lambda kv: -len(kv[0]))

    def rewrite(formula):
        if not formula or '!' not in formula:
            return formula
        parts = re.split(r'("(?:[^"]|"")*")', formula)
        for i in range(0, len(parts), 2):
            seg = parts[i]
            for old, new in pairs:
                seg = seg.replace("'" + old + "'!", "'" + new + "'!")
                seg = re.sub(r"(?<![\w'])" + re.escape(old) + r"!", "'" + new + "'!", seg)
            parts[i] = seg
        return ''.join(parts)

    return rewrite


def read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    shared = []
    if 'xl/sharedStrings.xml' in zf.namelist():
        root = ET.fromstring(zf.read('xl/sharedStrings.xml'))
        for si in root:
            shared.append(''.join((t.text or '') for t in si.iter(N + 't')))
    return shared


def read_unlocked_styles(zf: zipfile.ZipFile) -> set[int]:
    unlocked_styles = set()
    styles = ET.fromstring(zf.read('xl/styles.xml'))
    cell_xfs = styles.find(N + 'cellXfs')
    if cell_xfs is not None:
        for i, xf in enumerate(cell_xfs):
            prot = xf.find(N + 'protection')
            if prot is not None and prot.attrib.get('locked') == '0':
                unlocked_styles.add(i)
    return unlocked_styles


def read_sheet_index(zf: zipfile.ZipFile):
    wb = ET.fromstring(zf.read('xl/workbook.xml'))
    rels = ET.fromstring(zf.read('xl/_rels/workbook.xml.rels'))
    relmap = {r.attrib['Id']: r.attrib['Target'] for r in rels}
    out = []
    for idx, s in enumerate(wb.find(N + 'sheets')):
        rid = s.attrib['{%s}id' % REL]
        target = relmap[rid]
        if not target.startswith('xl/'):
            target = 'xl/' + target.lstrip('/')
        out.append((s.attrib['name'], int(s.attrib.get('sheetId', idx + 1)), target))
    return wb, out


INSERT_SQL = '''INSERT OR REPLACE INTO cells
  (sheet_idx,row_num,col_num,value_kind,num_value,text_value,formula,style_id,unlocked)
  VALUES(?,?,?,?,?,?,?,?,?)'''


def ingest_workbook(conn: sqlite3.Connection, zf: zipfile.ZipFile, start_idx: int,
                    label: str, rename_map: dict | None = None,
                    with_defined_names: bool = True) -> int:
    """Ingest every sheet of ``zf`` into the DB starting at ``start_idx``.

    Returns the number of sheets ingested. ``rename_map`` renames sheets (and
    rewrites intra-workbook sheet references in formulas)."""
    shared = read_shared_strings(zf)
    unlocked_styles = read_unlocked_styles(zf)
    wb, sheet_list = read_sheet_index(zf)
    rewrite_refs = make_sheet_ref_rewriter(rename_map)
    rename_map = rename_map or {}

    sheets = []
    for i, (name, sheet_id, target) in enumerate(sheet_list):
        db_name = rename_map.get(name, name)
        sheets.append((start_idx + i, db_name, sheet_id, f'{label}:{target}'))
    conn.executemany('INSERT INTO sheets(sheet_idx,name,excel_sheet_id,path) VALUES(?,?,?,?)', sheets)

    if with_defined_names:
        dns = wb.find(N + 'definedNames')
        if dns is not None:
            name_rows = []
            for dn in dns:
                nm = dn.attrib.get('name')
                if not nm or nm.startswith('_xlnm.'):
                    continue
                local = dn.attrib.get('localSheetId')
                local = int(local) + start_idx if local is not None else -1
                ref = (dn.text or '').replace('[1]', '').replace('[2]', '')
                name_rows.append((nm.upper(), local, ref))
            conn.executemany('INSERT OR REPLACE INTO defined_names(name,local_sheet_idx,reference) VALUES(?,?,?)', name_rows)

    for i, (name, sheet_id, path) in enumerate(sheet_list):
        sheet_idx = start_idx + i
        print(f'[{sheet_idx+1:03d}] {rename_map.get(name, name)}', flush=True)
        xml = ET.fromstring(zf.read(path))
        shared_formulas = {}
        batch = []
        for c in xml.iter(N + 'c'):
            addr = c.attrib.get('r')
            if not addr:
                continue
            try:
                col, row = split_addr(addr)
            except ValueError:
                continue
            style_id = int(c.attrib.get('s', '0'))
            unlocked = 1 if style_id in unlocked_styles else 0
            ctype = c.attrib.get('t')
            f = c.find(N + 'f')
            v = c.find(N + 'v')
            formula = None
            if f is not None:
                ftype = f.attrib.get('t')
                si = f.attrib.get('si')
                if f.text:
                    formula = f.text
                    if ftype == 'shared' and si is not None:
                        shared_formulas[si] = (addr, formula)
                elif ftype == 'shared' and si in shared_formulas:
                    base_addr, base_formula = shared_formulas[si]
                    formula = translate_formula(base_formula, base_addr, addr)
            if formula is not None:
                formula = rewrite_refs(formula)

            kind = 'blank'
            num = None
            text = None
            if ctype == 's' and v is not None and v.text is not None:
                kind = 'text'
                ix = int(v.text)
                text = shared[ix] if 0 <= ix < len(shared) else ''
            elif ctype == 'inlineStr':
                kind = 'text'
                isel = c.find(N + 'is')
                text = ''.join((t.text or '') for t in isel.iter(N + 't')) if isel is not None else ''
            elif ctype == 'b':
                kind = 'bool'
                num = 1.0 if (v is not None and v.text == '1') else 0.0
            elif ctype == 'e':
                kind = 'error'
                text = v.text if v is not None else '#ERROR!'
            elif ctype == 'str':
                kind = 'text'
                text = v.text if v is not None and v.text is not None else ''
            elif v is not None and v.text is not None:
                kind = 'number'
                try:
                    num = float(v.text)
                except ValueError:
                    kind = 'text'
                    text = v.text
            elif formula is not None:
                kind = 'blank'

            if formula is not None or kind != 'blank' or unlocked:
                batch.append((sheet_idx, row, col, kind, num, text, formula, style_id, unlocked))
                if len(batch) >= 5000:
                    conn.executemany(INSERT_SQL, batch)
                    batch.clear()
        if batch:
            conn.executemany(INSERT_SQL, batch)
        conn.commit()

    return len(sheet_list)


def main():
    if DB.exists():
        DB.unlink()

    conn = sqlite3.connect(DB)
    conn.execute('PRAGMA journal_mode=OFF')
    conn.execute('PRAGMA synchronous=OFF')
    conn.execute('PRAGMA temp_store=MEMORY')
    conn.execute('PRAGMA page_size=32768')
    conn.execute('PRAGMA cache_size=-250000')

    conn.executescript('''
    CREATE TABLE sheets(
      sheet_idx INTEGER PRIMARY KEY,
      name TEXT NOT NULL UNIQUE,
      excel_sheet_id INTEGER,
      path TEXT NOT NULL
    );
    CREATE TABLE cells(
      sheet_idx INTEGER NOT NULL,
      row_num INTEGER NOT NULL,
      col_num INTEGER NOT NULL,
      value_kind TEXT NOT NULL DEFAULT 'blank',
      num_value REAL,
      text_value TEXT,
      formula TEXT,
      style_id INTEGER NOT NULL DEFAULT 0,
      unlocked INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY(sheet_idx,row_num,col_num)
    ) WITHOUT ROWID;
    CREATE TABLE defined_names(
      name TEXT NOT NULL,
      local_sheet_idx INTEGER,
      reference TEXT,
      PRIMARY KEY(name, local_sheet_idx)
    ) WITHOUT ROWID;
    CREATE INDEX idx_cells_sheet_col_row ON cells(sheet_idx,col_num,row_num);
    ''')

    next_idx = 0
    with zipfile.ZipFile(XLSX) as zf:
        next_idx += ingest_workbook(conn, zf, next_idx, 'Planilha_correcao.xlsx')

    for spec in EXTRA_WORKBOOKS:
        path = DATA / spec['file']
        if not path.exists():
            print(f'AVISO: workbook extra ausente, pulando: {spec["file"]}')
            continue
        with zipfile.ZipFile(path) as zf:
            next_idx += ingest_workbook(conn, zf, next_idx, spec['file'],
                                        rename_map=spec.get('rename'),
                                        with_defined_names=False)

    conn.execute('ANALYZE')
    conn.execute('VACUUM')
    conn.close()
    print(f'Created {DB} ({DB.stat().st_size/1024/1024:.1f} MB)')


if __name__ == '__main__':
    main()
