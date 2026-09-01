from __future__ import annotations

import datetime as _dt
import inspect
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import schedula as sh
import formulas

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / 'data' / 'neuro_normas.db'

CELL_RE = re.compile(r'^\$?([A-Z]{1,3})\$?(\d+)$', re.I)
RANGE_RE = re.compile(r'^\$?([A-Z]{1,3})\$?(\d+):\$?([A-Z]{1,3})\$?(\d+)$', re.I)
COL_RE = re.compile(r'^\$?([A-Z]{1,3}):\$?([A-Z]{1,3})$', re.I)
ROW_RE = re.compile(r'^\$?(\d+):\$?(\d+)$')

RAW_HEADER_RE = re.compile(
    r'(?i)(pontos?\s*brutos?|pontua[cç][aã]o\s*bruta|escores?\s*brutos?|resultado\s*bruto|\bescore bruto\b|\bPB\b|\bpts?\.?\s*(?:brutos?|brts?|bts?)\b)'
)
PROFILE_LABELS = {
    'name': re.compile(r'(?i)^\s*nome\s*:?\s*$'),
    'education': re.compile(r'(?i)escolaridade|escolar'),
    'sex': re.compile(r'(?i)^\s*sexo\s*:?\s*$|g[eê]nero'),
    'birth_date': re.compile(r'(?i)^\s*data\s*(de\s*)?(?:nascimento|nasc(?:to|imento))\s*:?.*$'),
    'application_date': re.compile(r'(?i)^\s*data\s*(de\s*)?(?:aplica[cç][aã]o|aplic\.?)\s*:?.*$|^\s*data\s*do\s*teste\s*:?.*$'),
}
PROFILE_EXCLUDE_RE = re.compile(
    r'(?i)(nome|sexo|g[eê]nero|escolar|nascimento|aplica[cç][aã]o|idade|amostra|faixa|norma|intervalo|confian[cç]a|informante|vers[aã]o|tipo|grupo|profissional|respondente)'
)
RESULT_HEADER_RE = re.compile(
    r'(?i)(percentil|classifica|ponderad|composto|qi\b|q\.i|[ií]ndice|escore[-\s]?t|z[-\s]?score|stanine|resultado|tempo|custo|inibi|flexib|aprendiz|interfer|dom[ií]nio|subdom[ií]nio|faixa|idade mental|frequ[eê]ncia|padroniz|normatiz|quociente|pontua[cç][aã]o)'
)
GENERIC_HEADER_RE = re.compile(
    r'(?i)^(teste|subteste|escala|dom[ií]nio|[ií]ndice|fator|habilidade|processo|vari[aá]vel|item|resultado)$'
)

TEST_EXCLUDE_RE = re.compile(
    r'(?i)(norma|normas|nomas|antigas|formata[cç][aã]o|funcoes|fun[cç][oõ]es|menu|in[ií]cio|cadastro|id-usu[aá]rio|abas|protocolo|recibo|tab[_\s-]*convers|provas\s*seabra)'
)

CHART_GROUPS = [
    (re.compile(r'(?i)WISC|WAIS|WASI'), 'wechsler'),
    (re.compile(r'(?i)RAVLT|HVLT|BVMT'), 'learning_curve'),
    (re.compile(r'(?i)FDT|STROOP|HAYLING|GO-NO|TRILHAS|TOL|WISCONSIN|WSCT'), 'executive'),
    (re.compile(r'(?i)VINELAND|VIN_3|SRS|BRIEF|ETDAH|SCARED|CBCL|SDQ|SNAP|BDEFS|BAMS'), 'domains'),
    (re.compile(r'(?i)TDE|PROLEC|PED|THCP|NOMEA|ARITM|NEUPSILIN|NEPSY'), 'academic'),
    (re.compile(r'(?i)CORSI|FIGREY|7FIG|TOKEN|TFV|BPA|D2|AC|BFP|PFISTER'), 'profile'),
]


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


def a1(col: int, row: int) -> str:
    return f'{num_to_col(col)}{row}'


def parse_cell(addr: str):
    m = CELL_RE.match(addr.strip())
    if not m:
        return None
    return col_to_num(m.group(1)), int(m.group(2))


def excel_serial(date_value: str | _dt.date | _dt.datetime | None):
    if not date_value:
        return sh.EMPTY
    if isinstance(date_value, str):
        try:
            d = _dt.date.fromisoformat(date_value[:10])
        except ValueError:
            return date_value
    elif isinstance(date_value, _dt.datetime):
        d = date_value.date()
    else:
        d = date_value
    return (d - _dt.date(1899, 12, 30)).days


def normalize_formula_text(formula: str) -> str:
    f = (formula or '').strip()
    if not f:
        return ''
    if not f.startswith('='):
        f = '=' + f
    # Remove external-book markers carried by the source file.
    f = re.sub(r"'\[[^\]]+\]([^']+)'!", r"'\1'!", f)
    f = re.sub(r'\[[^\]]+\]([^!]+)!', r'\1!', f)
    return f


def clean_text(value: Any) -> str:
    if value is None or value is sh.EMPTY:
        return ''
    return str(value).replace('\n', ' ').strip()


def internal_scalar(value: Any):
    """Unwrap 1-cell formula arrays before feeding them into other formulas."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray) and value.size == 1:
        item = value.reshape(-1)[0]
        if item is value:
            return value
        return internal_scalar(item)
    return value


def scalarize(value: Any):
    if value is sh.EMPTY:
        return ''
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, np.ndarray):
        if value.size == 1:
            return scalarize(value.reshape(-1)[0])
        return [[scalarize(x) for x in row] for row in value.tolist()]
    # formulas/schedula errors stringify cleanly (#VALUE!, #N/A, etc.)
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return None
            if abs(value - round(value)) < 1e-12:
                return int(round(value))
        return value
    if isinstance(value, bool):
        return value
    if value is None:
        return ''
    s = str(value)
    if s == 'empty':
        return ''
    return s


class WorkbookEngine:
    def __init__(self, db_path: Path | str = DB_PATH):
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.parser = formulas.Parser()
        self.sheet_name_to_idx = {}
        self.sheet_idx_to_name = {}
        for r in self.conn.execute('SELECT sheet_idx,name FROM sheets ORDER BY sheet_idx'):
            self.sheet_name_to_idx[r['name'].upper()] = r['sheet_idx']
            self.sheet_idx_to_name[r['sheet_idx']] = r['name']
        self._cell_cache = {}
        self._formula_cache = {}
        self._catalog_cache = None
        self._meta_cache = {}
        self._defined_cache = {}

    def close(self):
        self.conn.close()

    def sheet_name(self, name: str) -> str:
        idx = self.sheet_name_to_idx.get(name.strip("'").upper())
        if idx is None:
            raise KeyError(f'Aba não encontrada: {name}')
        return self.sheet_idx_to_name[idx]

    def sheet_idx(self, name: str) -> int:
        key = name.strip("'").upper()
        if key not in self.sheet_name_to_idx:
            raise KeyError(f'Aba não encontrada: {name}')
        return self.sheet_name_to_idx[key]

    def list_tests(self):
        out = []
        for idx in sorted(self.sheet_idx_to_name):
            name = self.sheet_idx_to_name[idx]
            if TEST_EXCLUDE_RE.search(name):
                continue
            # Require at least some content/formula activity.
            count = self.conn.execute(
                'SELECT count(*) FROM cells WHERE sheet_idx=? AND (formula IS NOT NULL OR value_kind<>\'blank\')', (idx,)
            ).fetchone()[0]
            if count < 3:
                continue
            out.append(name)
        return out

    @lru_cache(maxsize=200000)
    def _get_cell_row(self, sheet_idx: int, row: int, col: int):
        return self.conn.execute(
            'SELECT * FROM cells WHERE sheet_idx=? AND row_num=? AND col_num=?', (sheet_idx,row,col)
        ).fetchone()

    def base_value(self, row: sqlite3.Row | None):
        if row is None:
            return sh.EMPTY
        kind = row['value_kind']
        if kind == 'number':
            return row['num_value']
        if kind == 'bool':
            return bool(row['num_value'])
        if kind in ('text','error'):
            return row['text_value'] or ''
        return sh.EMPTY

    def _defined_reference(self, name: str, local_sheet_idx: int):
        key = (name.upper(), local_sheet_idx)
        if key in self._defined_cache:
            return self._defined_cache[key]
        r = self.conn.execute(
            'SELECT reference FROM defined_names WHERE name=? AND local_sheet_idx=?', (name.upper(), local_sheet_idx)
        ).fetchone()
        if r is None:
            r = self.conn.execute(
                'SELECT reference FROM defined_names WHERE name=? AND local_sheet_idx=-1', (name.upper(),)
            ).fetchone()
        ref = r['reference'] if r else None
        self._defined_cache[key] = ref
        return ref

    def _split_ref(self, ref: str, current_sheet: str):
        s = ref.strip()
        # Formulas parser may keep apostrophes around sheet names with spaces.
        if '!' in s:
            sheet_part, coord = s.rsplit('!', 1)
            sheet = sheet_part.strip().strip("'")
        else:
            sheet, coord = current_sheet, s
        coord = coord.replace('$','').strip()
        return self.sheet_name(sheet), coord

    def _resolve_named_or_ref(self, ref: str, current_sheet: str, overrides, stack):
        try:
            sheet, coord = self._split_ref(ref, current_sheet)
        except KeyError:
            sheet, coord = current_sheet, ref.replace('$','').strip()

        # Direct A1 / A1:B2 refs.
        if CELL_RE.match(coord):
            c,r = parse_cell(coord)
            return self.evaluate_cell(sheet,r,c,overrides,stack)
        m = RANGE_RE.match(coord)
        if m:
            c1,r1,c2,r2 = col_to_num(m.group(1)),int(m.group(2)),col_to_num(m.group(3)),int(m.group(4))
            if c1>c2: c1,c2=c2,c1
            if r1>r2: r1,r2=r2,r1
            return self.evaluate_range(sheet,r1,c1,r2,c2,overrides,stack)

        # Whole column/row refs are bounded to actual stored cells in the sheet.
        m = COL_RE.match(coord)
        if m:
            c1,c2=col_to_num(m.group(1)),col_to_num(m.group(2))
            mm=self.conn.execute('SELECT min(row_num),max(row_num) FROM cells WHERE sheet_idx=? AND col_num BETWEEN ? AND ?',
                                 (self.sheet_idx(sheet),min(c1,c2),max(c1,c2))).fetchone()
            r1,r2=(mm[0] or 1),(mm[1] or 1)
            return self.evaluate_range(sheet,r1,min(c1,c2),r2,max(c1,c2),overrides,stack)
        m = ROW_RE.match(coord)
        if m:
            r1,r2=int(m.group(1)),int(m.group(2))
            mm=self.conn.execute('SELECT min(col_num),max(col_num) FROM cells WHERE sheet_idx=? AND row_num BETWEEN ? AND ?',
                                 (self.sheet_idx(sheet),min(r1,r2),max(r1,r2))).fetchone()
            c1,c2=(mm[0] or 1),(mm[1] or 1)
            return self.evaluate_range(sheet,min(r1,r2),c1,max(r1,r2),c2,overrides,stack)

        # Named range.
        local_idx = self.sheet_idx(current_sheet)
        named = self._defined_reference(coord, local_idx)
        if named:
            return self._resolve_named_or_ref(named, current_sheet, overrides, stack)

        # Unknown name: preserve Excel-like missing reference rather than crash.
        return sh.EMPTY

    def _compiled_formula(self, formula: str):
        f = normalize_formula_text(formula)
        if f in self._formula_cache:
            return self._formula_cache[f]
        try:
            _, builder = self.parser.ast(f)
            compiled = builder.compile()
        except Exception as exc:
            compiled = exc
        self._formula_cache[f] = compiled
        return compiled

    def evaluate_cell(self, sheet: str, row: int, col: int, overrides: dict, stack: set):
        canonical_sheet = self.sheet_name(sheet)
        key=(canonical_sheet.upper(),row,col)
        if key in overrides:
            val=overrides[key]
            return sh.EMPTY if val in (None,'') else val
        cache_key=(canonical_sheet.upper(),row,col,overrides.get('__version__',0))
        if cache_key in self._cell_cache:
            return self._cell_cache[cache_key]
        if key in stack:
            return '#CIRC!'
        stack.add(key)
        dbrow=self._get_cell_row(self.sheet_idx(canonical_sheet),row,col)
        if dbrow is None:
            out=sh.EMPTY
        elif dbrow['formula']:
            compiled=self._compiled_formula(dbrow['formula'])
            if isinstance(compiled, Exception):
                # Fall back to cached value if formula parsing fails.
                out=self.base_value(dbrow)
            else:
                args=[]
                try:
                    for ref in compiled.inputs.keys():
                        args.append(self._resolve_named_or_ref(ref, canonical_sheet, overrides, stack))
                    out=compiled(*args)
                except Exception:
                    out=self.base_value(dbrow)
        else:
            out=self.base_value(dbrow)
        stack.remove(key)
        out=internal_scalar(out)
        self._cell_cache[cache_key]=out
        return out

    def evaluate_range(self, sheet: str, r1: int, c1: int, r2: int, c2: int, overrides: dict, stack: set):
        # Protect against accidental enormous whole-sheet arrays.
        total=(r2-r1+1)*(c2-c1+1)
        if total>250000:
            # Most normative functions need only non-empty records; clamp using existing range bounds.
            rows=self.conn.execute(
                'SELECT min(row_num),max(row_num),min(col_num),max(col_num) FROM cells WHERE sheet_idx=? AND row_num BETWEEN ? AND ? AND col_num BETWEEN ? AND ?',
                (self.sheet_idx(sheet),r1,r2,c1,c2)
            ).fetchone()
            if rows and rows[0] is not None:
                r1,r2=max(r1,rows[0]),min(r2,rows[1])
                c1,c2=max(c1,rows[2]),min(c2,rows[3])
        arr=[]
        for r in range(r1,r2+1):
            row=[]
            for c in range(c1,c2+1):
                row.append(self.evaluate_cell(sheet,r,c,overrides,stack))
            arr.append(row)
        return np.array(arr,dtype=object)

    def evaluate_address(self, sheet: str, addr: str, overrides: dict | None = None):
        overrides=overrides or {'__version__':0}
        sheet,coord=self._split_ref(addr,sheet)
        if CELL_RE.match(coord):
            c,r=parse_cell(coord)
            return scalarize(self.evaluate_cell(sheet,r,c,overrides,set()))
        return scalarize(self._resolve_named_or_ref(addr,sheet,overrides,set()))

    # ---------- catalog / form discovery ----------
    def _sheet_rows(self, sheet: str):
        idx=self.sheet_idx(sheet)
        rows=defaultdict(dict)
        for r in self.conn.execute(
            'SELECT row_num,col_num,value_kind,num_value,text_value,formula,unlocked FROM cells WHERE sheet_idx=? ORDER BY row_num,col_num', (idx,)
        ):
            val=self.base_value(r)
            rows[r['row_num']][r['col_num']]={
                'value': val,
                'formula': r['formula'],
                'unlocked': bool(r['unlocked']),
                'kind': r['value_kind'],
            }
        return rows

    def _nearest_row_label(self, rows, row: int, col: int, max_left=10):
        candidates=[]
        for c in range(max(1,col-max_left),col):
            e=rows.get(row,{}).get(c)
            if not e: continue
            txt=clean_text(e['value'])
            if txt and not RAW_HEADER_RE.search(txt):
                candidates.append((c,txt))
        if not candidates:
            return ''
        # Prefer the nearest meaningful text; skip punctuation-only/generic codes.
        # Prefer descriptive labels over short subtest codes like (CB).
        descriptive=[(c,t) for c,t in candidates if len(t)>=4 and not (re.fullmatch(r'\([A-ZÁÉÍÓÚÇ0-9 -]{1,5}\)',t.upper()) or re.fullmatch(r'[A-Z]{1,3}',t.upper()))]
        if descriptive:
            return descriptive[-1][1]
        for _,txt in reversed(candidates):
            if len(txt)>=2:
                return txt
        return candidates[-1][1]

    def _nearest_col_header(self, rows, row: int, col: int, max_up=8):
        for r in range(row-1,max(0,row-max_up)-1,-1):
            e=rows.get(r,{}).get(col)
            if e:
                txt=clean_text(e['value'])
                if txt:
                    return txt
        return ''

    def discover_profile_cells(self, sheet: str, rows=None):
        rows=rows or self._sheet_rows(sheet)
        found={}
        for rnum,row in rows.items():
            if rnum>25: continue
            for c,e in row.items():
                txt=clean_text(e['value'])
                if not txt: continue
                for key,rx in PROFILE_LABELS.items():
                    if key in found or not rx.search(txt):
                        continue
                    # Scan to the right. Prefer an unlocked/value cell; merged labels often leave gaps.
                    target=None
                    for cc in range(c+1,c+6):
                        ce=row.get(cc)
                        if ce and (ce['unlocked'] or ce['formula'] or clean_text(ce['value'])):
                            target=cc; break
                    if target:
                        found[key]=a1(target,rnum)
        return found

    def _formula_direct_refs(self, sheet: str, rows):
        """Fast local-reference scan used only for input discovery (not calculation)."""
        counter=Counter()
        rx=re.compile(r'(?<![A-Z0-9_!])\$?([A-Z]{1,3})\$?(\d+)',re.I)
        for row in rows.values():
            for e in row.values():
                formula=e.get('formula')
                if not formula:
                    continue
                # Ignore refs written inside quoted string literals.
                parts=re.split(r'"(?:[^"]|"")*"',formula)
                for part in parts:
                    for m in rx.finditer(part):
                        coord=f'{m.group(1).upper()}{m.group(2)}'
                        counter[coord]+=1
        return counter

    def discover_raw_fields(self, sheet: str, rows=None):
        rows=rows or self._sheet_rows(sheet)
        headers=[]
        for rnum,row in rows.items():
            for c,e in row.items():
                txt=clean_text(e['value'])
                if txt and RAW_HEADER_RE.search(txt):
                    headers.append((rnum,c,txt))

        fields={}
        for hr,hc,htxt in headers:
            # Case 1: column header (e.g. WISC E9 "Pontos Brutos")
            if len(htxt)<45 and not re.search(r'(?i)total\s+',htxt):
                misses=0
                for rr in range(hr+1, min(hr+85, max(rows.keys(), default=hr)+1)):
                    ce=rows.get(rr,{}).get(hc)
                    label=self._nearest_row_label(rows,rr,hc,12)
                    if ce is None and not label:
                        misses+=1
                        if misses>=5: break
                        continue
                    misses=0
                    if not ce:
                        continue
                    # Stop at obvious new section heading in this column.
                    celltxt=clean_text(ce['value'])
                    if celltxt and RAW_HEADER_RE.search(celltxt):
                        break
                    # A text value in the score column usually marks the next section/header.
                    if celltxt and not ce['formula'] and ce['kind']=='text' and not re.fullmatch(r'[-+]?\d+(?:[.,]\d+)?',celltxt):
                        break
                    if label and not RESULT_HEADER_RE.search(label):
                        addr=a1(hc,rr)
                        fields[addr]={
                            'cell':addr,
                            'label':label,
                            'current':scalarize(ce['value']),
                            'source':'header-column',
                            'allow_override_formula':bool(ce['formula']),
                        }
            # Case 2: row label "Total Pontos Brutos:" and value to the right.
            for cc in range(hc+1,hc+6):
                ce=rows.get(hr,{}).get(cc)
                if ce and (ce['formula'] or ce['unlocked'] or ce['kind'] in ('number','blank')):
                    label=htxt or self._nearest_row_label(rows,hr,hc,12)
                    addr=a1(cc,hr)
                    fields.setdefault(addr,{
                        'cell':addr,'label':label,'current':scalarize(ce['value']),
                        'source':'header-row','allow_override_formula':bool(ce['formula'])
                    })
                    break

        # Fallback/augmentation: unlocked scalar cells referenced by formulas.
        refs=self._formula_direct_refs(sheet,rows)
        for addr,n in refs.most_common():
            pos=parse_cell(addr)
            if not pos: continue
            c,r=pos
            ce=rows.get(r,{}).get(c)
            if not ce or not ce['unlocked'] or ce['formula']:
                continue
            label=self._nearest_row_label(rows,r,c,12) or self._nearest_col_header(rows,r,c,8)
            if not label or PROFILE_EXCLUDE_RE.search(label):
                continue
            # Prefer numerical/blank score-like cells and exclude obvious UI actions.
            val=ce['value']
            # schedula.EMPTY is a string-like sentinel; treat it as an Excel blank.
            if val is not sh.EMPTY and isinstance(val,str) and val and not re.fullmatch(r'[-+]?\d+(?:[.,]\d+)?',val.strip()):
                continue
            fields.setdefault(addr,{
                'cell':addr,'label':label,'current':scalarize(val),
                'source':'formula-input','allow_override_formula':False
            })

        # De-duplicate pathological labels and trim non-score buttons.
        out=[]
        seen_labels=Counter()
        for addr,f in sorted(fields.items(), key=lambda kv:(parse_cell(kv[0])[1],parse_cell(kv[0])[0])):
            label=re.sub(r'\s+',' ',f['label']).strip(' :;-')
            if not label or re.search(r'(?i)(ir para|topo|voltar|imprimir|salvar|gr[aá]fico)',label):
                continue
            seen_labels[label]+=1
            if seen_labels[label]>1:
                f['label']=f'{label} ({addr})'
            else:
                f['label']=label
            out.append(f)
        return out[:300]


    def discover_summary_raw_fields(self, sheet: str, rows=None, tables=None):
        """Discover compact raw-score inputs from result tables.

        Many questionnaire sheets contain hundreds of item-response cells, but their
        normative conversion is driven by a much smaller set of total/subscale raw
        scores.  When a result table exposes a 'Pontos Brutos' (or abbreviated)
        column, those cells are the preferred user inputs. Formula cells are safe to
        override for the current calculation only; the source workbook/database is
        never modified.
        """
        rows = rows or self._sheet_rows(sheet)
        tables = tables or self.discover_tables(sheet, rows)
        found = {}
        for table in tables:
            raw_indexes = [i for i,c in enumerate(table['columns']) if RAW_HEADER_RE.search(clean_text(c.get('label','')))]
            if not raw_indexes:
                continue
            for row in table['rows']:
                for ix in raw_indexes:
                    if ix >= len(row['cells']):
                        continue
                    cell = row['cells'][ix]
                    addr = cell['cell']
                    c,r = parse_cell(addr)
                    db = rows.get(r,{}).get(c)
                    if not db:
                        continue
                    dbtxt = clean_text(db['value'])
                    # A literal text cell under a raw-score header is usually another
                    # label (e.g. 'Percentil:'), not a score input.
                    if not db.get('formula') and dbtxt and not re.fullmatch(r'[-+]?\d+(?:[.,]\d+)?', dbtxt):
                        continue
                    # Find the best descriptive label in this same result row.
                    label = ''
                    # Prefer columns to the left, then any other textual table column.
                    order = list(range(ix-1,-1,-1)) + [j for j in range(len(row['cells'])) if j != ix]
                    for j in order:
                        other = row['cells'][j]
                        txt = clean_text(other.get('cached',''))
                        if not txt or RAW_HEADER_RE.search(txt) or RESULT_HEADER_RE.fullmatch(txt):
                            continue
                        if re.fullmatch(r'[-+]?\d+(?:[.,]\d+)?', txt):
                            continue
                        if len(txt) > 140:
                            continue
                        label = txt
                        break
                    if not label:
                        label = self._nearest_row_label(rows,r,c,16) or f'Ponto bruto {addr}'
                    # Skip obvious instructional/classification rows.
                    if re.search(r'(?i)(classifica[cç][aã]o|manual|descri[cç][aã]o|interpreta[cç][aã]o|aten[cç][aã]o!|sistema de)', label):
                        continue
                    found.setdefault(addr,{
                        'cell':addr,
                        'label':re.sub(r'\s+',' ',label).strip(' :;-'),
                        'current':scalarize(db['value']),
                        'source':'summary-raw',
                        'allow_override_formula':True,
                    })
        # De-duplicate display labels while keeping every distinct score cell.
        out=[]; seen=Counter()
        for addr,f in sorted(found.items(), key=lambda kv:(parse_cell(kv[0])[1],parse_cell(kv[0])[0])):
            label=f['label'] or f'Ponto bruto {addr}'
            seen[label]+=1
            if seen[label]>1:
                f['label']=f'{label} ({addr})'
            out.append(f)
        return out[:180]

    def discover_parameter_fields(self, sheet: str, rows=None, raw_cells=None, profile_cells=None):
        rows=rows or self._sheet_rows(sheet)
        raw_cells=set(raw_cells or [])
        profile_cells=set(profile_cells or [])
        refs=self._formula_direct_refs(sheet,rows)
        out=[]
        for addr,n in refs.most_common():
            if addr in raw_cells or addr in profile_cells:
                continue
            c,r=parse_cell(addr)
            ce=rows.get(r,{}).get(c)
            if not ce or not ce['unlocked'] or ce['formula']:
                continue
            label=self._nearest_row_label(rows,r,c,12) or self._nearest_col_header(rows,r,c,8)
            val=scalarize(ce['value'])
            if not label: continue
            # Parameters are typically text selectors or percentages, not score values.
            if isinstance(val,str) and val.strip() and not re.fullmatch(r'[-+]?\d+(?:[.,]\d+)?',val.strip()):
                out.append({'cell':addr,'label':label,'current':val,'references':n})
        return out[:30]

    def discover_tables(self, sheet: str, rows=None):
        rows=rows or self._sheet_rows(sheet)
        candidates=[]
        for rnum,row in rows.items():
            # Treat only literal text cells as headers; cached text produced by formulas is output, not a header.
            headers=[]
            for c,e in row.items():
                txt=clean_text(e['value'])
                if txt and not e['formula'] and e['kind']=='text':
                    headers.append((c,txt))
            if len(headers)<2:
                continue
            if not any(RESULT_HEADER_RE.search(t) or RAW_HEADER_RE.search(t) for _,t in headers):
                continue
            # Exclude explanatory paragraphs.
            compact=[(c,t) for c,t in headers if len(t)<90]
            if len(compact)<2:
                continue
            candidates.append((rnum,compact))

        # When a section title is immediately above a real header row, keep the row with more columns.
        compact_candidates=[]
        for hr,headers in candidates:
            replaced=False
            for i,(ehr,eheaders) in enumerate(compact_candidates):
                if abs(hr-ehr)<=1:
                    if len(headers)>len(eheaders):
                        compact_candidates[i]=(hr,headers)
                    replaced=True
                    break
            if not replaced:
                compact_candidates.append((hr,headers))

        tables=[]
        used_rows=set()
        for hr,headers in compact_candidates:
            if any(abs(hr-x)<2 for x in used_rows):
                continue
            cols=[c for c,_ in headers]
            # Limit to a reasonable table width; keep explicit header columns only.
            header_map={c:t for c,t in headers}
            data=[]
            blanks=0
            for rr in range(hr+1, min(hr+61,max(rows.keys(),default=hr)+1)):
                rec=[]
                nonblank=0
                formulas_count=0
                for c in cols:
                    e=rows.get(rr,{}).get(c)
                    if e:
                        val=e['value']
                        if e['formula']: formulas_count+=1
                        if clean_text(val) or e['formula']:
                            nonblank+=1
                        rec.append({'cell':a1(c,rr),'cached':scalarize(val),'formula':bool(e['formula'])})
                    else:
                        rec.append({'cell':a1(c,rr),'cached':'','formula':False})
                if nonblank==0:
                    blanks+=1
                    if blanks>=3: break
                    continue
                blanks=0
                if nonblank>=1:
                    data.append({'row':rr,'cells':rec})
            if len(data)>=2:
                title=' / '.join(t for _,t in headers[:2])
                tables.append({
                    'header_row':hr,
                    'title':title,
                    'columns':[{'col':c,'label':header_map[c]} for c in cols],
                    'rows':data[:45],
                })
                used_rows.add(hr)
            if len(tables)>=8:
                break
        return tables

    def chart_type(self, sheet: str):
        for rx,kind in CHART_GROUPS:
            if rx.search(sheet):
                return kind
        return 'profile'

    def catalog(self, refresh=False):
        if self._catalog_cache is None or refresh:
            self._catalog_cache=[{
                'name':name,
                'chart_type':self.chart_type(name),
            } for name in self.list_tests()]
        return self._catalog_cache

    def test_meta(self, test_name: str):
        canonical=self.sheet_name(test_name)
        if canonical in self._meta_cache:
            return self._meta_cache[canonical]
        if canonical not in self.list_tests():
            raise KeyError(test_name)
        rows=self._sheet_rows(canonical)
        profile=self.discover_profile_cells(canonical,rows)
        raw_detail=self.discover_raw_fields(canonical,rows)
        tables=self.discover_tables(canonical,rows)
        summary_raw=self.discover_summary_raw_fields(canonical,rows,tables)
        # The requested workflow is PB-only. Explicit PB headers are highest priority;
        # result-table PB cells supplement them. Item-level formula inputs are used only
        # when the workbook exposes no compact bruto/subscale entry at all.
        compact = {}
        for f in raw_detail:
            if f.get('source') in ('header-column','header-row'):
                compact[f['cell']] = f
        for f in summary_raw:
            compact.setdefault(f['cell'], f)
        raw = sorted(compact.values(), key=lambda f:(parse_cell(f['cell'])[1],parse_cell(f['cell'])[0])) if compact else raw_detail
        params=self.discover_parameter_fields(canonical,rows,[x['cell'] for x in raw],profile.values())
        meta={
            'name':canonical,
            'raw_fields':raw,
            'detail_fields':raw_detail if summary_raw else [],
            'input_mode':'pontos_brutos' if compact else 'campos_origem',
            'profile_cells':profile,
            'parameters':params,
            'tables':tables,
            'chart_type':self.chart_type(canonical),
        }
        self._meta_cache[canonical]=meta
        return meta

    def build_overrides(self, meta: dict, patient: dict, raw_scores: dict, parameters: dict | None = None):
        sheet=meta['name']
        version=hash(json.dumps([patient,raw_scores,parameters or {}],sort_keys=True,default=str)) & 0x7FFFFFFF
        overrides={'__version__':version}
        def put(addr,val):
            if not addr: return
            c,r=parse_cell(addr)
            overrides[(sheet.upper(),r,c)] = val

        pmap=meta.get('profile_cells',{})
        put(pmap.get('name'), patient.get('name',''))
        put(pmap.get('education'), patient.get('education',''))
        sex=patient.get('sex','')
        if sex in ('M','m','male','Masculino'): sex='Masculino'
        elif sex in ('F','f','female','Feminino'): sex='Feminino'
        put(pmap.get('sex'), sex)
        put(pmap.get('birth_date'), excel_serial(patient.get('birth_date')))
        put(pmap.get('application_date'), excel_serial(patient.get('application_date')))

        # Células com fórmula na planilha (ex.: somas dos ponderados / índices do WISC).
        # Sem um valor digitado, elas NÃO são sobrescritas: a planilha as recalcula
        # automaticamente a partir dos pontos brutos já aplicados.
        formula_backed={
            f['cell']
            for f in (meta.get('raw_fields',[]) + meta.get('detail_fields',[]))
            if f.get('allow_override_formula')
        }
        for addr,val in (raw_scores or {}).items():
            if val is None or val=='':
                if addr in formula_backed:
                    continue
                val=sh.EMPTY
            elif isinstance(val,str):
                txt=val.strip().replace(',','.')
                try: val=float(txt)
                except ValueError: pass
            c,r=parse_cell(addr)
            overrides[(sheet.upper(),r,c)]=val
        for addr,val in (parameters or {}).items():
            c,r=parse_cell(addr)
            overrides[(sheet.upper(),r,c)]=val if val not in (None,'') else sh.EMPTY
        return overrides

    def score(self, test_name: str, patient: dict, raw_scores: dict, parameters: dict | None = None):
        meta=self.test_meta(test_name)
        overrides=self.build_overrides(meta,patient,raw_scores,parameters)
        # Clear per-evaluation memo to prevent unbounded growth and ensure override-sensitive values.
        self._cell_cache.clear()
        evaluated_tables=[]
        for table in meta['tables']:
            rows_out=[]
            for row in table['rows']:
                vals=[]
                for cell in row['cells']:
                    try:
                        val=self.evaluate_address(test_name,cell['cell'],overrides)
                    except Exception as exc:
                        val=f'#ERRO: {type(exc).__name__}'
                    vals.append(val)
                # Suppress rows that are wholly blank after recalculation.
                if any(v not in ('',None) for v in vals):
                    rows_out.append({'row':row['row'],'values':vals,'cells':[x['cell'] for x in row['cells']]})
            if rows_out:
                evaluated_tables.append({
                    'title':table['title'],
                    'header_row':table['header_row'],
                    'columns':table['columns'],
                    'rows':rows_out,
                })

        # Also recalc each raw field's current value to report exactly what was applied.
        applied=[]
        for f in meta['raw_fields']:
            applied.append({**f,'value':self.evaluate_address(test_name,f['cell'],overrides)})

        return {
            'test':test_name,
            'chart_type':meta['chart_type'],
            'raw_scores':applied,
            'tables':evaluated_tables,
            'profile_cells':meta['profile_cells'],
            'parameters':meta['parameters'],
        }


if __name__ == '__main__':
    eng=WorkbookEngine()
    print('tests',len(eng.list_tests()))
    meta=eng.test_meta('WISC-IV')
    print('WISC raw',meta['raw_fields'][:20])
    print('WISC profile',meta['profile_cells'])
    print('WISC tables',[(t['header_row'],[c['label'] for c in t['columns']]) for t in meta['tables'][:4]])
