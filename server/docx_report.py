"""Geração do laudo neuropsicológico integrado em .docx (Word).

Usa apenas os dados já produzidos pelo fluxo (paciente + resultado estruturado da
IA + testes corrigidos). Não chama serviços externos. O texto continua exigindo
revisão e assinatura de profissional habilitado.
"""
from __future__ import annotations

import io
from datetime import date
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

INK = RGBColor(0x1B, 0x23, 0x33)
ACCENT = RGBColor(0x2F, 0x57, 0xB8)
MUTED = RGBColor(0x60, 0x6A, 0x80)

SECTION_ORDER = [
    ("identificacao_e_demanda", "Identificação e demanda"),
    ("historia_clinica_e_desenvolvimental", "História clínica e desenvolvimental"),
    ("procedimentos_e_instrumentos", "Procedimentos e instrumentos"),
    ("resultados_por_dominio", "Resultados por domínio"),
    ("integracao_neuropsicologica", "Integração neuropsicológica"),
    ("hipoteses_e_diferenciais", "Hipóteses e diagnósticos diferenciais"),
    ("recomendacoes", "Recomendações"),
    ("limitacoes", "Limitações"),
    ("conclusao", "Conclusão"),
]


def _clean(v: Any) -> str:
    return "" if v is None else str(v).strip()


def _style(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.font.color.rgb = INK
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15


def _heading(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text.upper())
    run.bold = True
    run.font.size = Pt(11)
    run.font.color.rgb = ACCENT


def _body(doc: Document, text: str) -> None:
    text = _clean(text)
    if not text:
        return
    for para in text.split("\n"):
        para = para.strip()
        if para:
            doc.add_paragraph(para)


def _bullets(doc: Document, items: list) -> None:
    for item in items or []:
        item = _clean(item)
        if item:
            doc.add_paragraph(item, style="List Bullet")


def _domain_block(doc: Document, entries: list) -> None:
    for entry in entries or []:
        if not isinstance(entry, dict):
            _body(doc, entry)
            continue
        name = _clean(entry.get("dominio"))
        if name:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(6)
            r = p.add_run(name)
            r.bold = True
        _body(doc, entry.get("descricao"))
        ev = [e for e in (entry.get("evidencias") or []) if _clean(e)]
        if ev:
            p = doc.add_paragraph()
            p.add_run("Evidências: ").italic = True
            p.add_run("; ".join(_clean(e) for e in ev))


def build_integrated_docx(patient: dict, report: dict, tests: list[str] | None = None) -> bytes:
    doc = Document()
    _style(doc)

    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Pt(64)
    sec.top_margin = sec.bottom_margin = Pt(56)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    tr = title.add_run("Laudo neuropsicológico")
    tr.bold = True
    tr.font.size = Pt(18)
    tr.font.color.rgb = INK

    # Cabeçalho de identificação
    meta_rows = [
        ("Nome", _clean(patient.get("name")) or "—"),
        ("Data de nascimento", _clean(patient.get("birth_date")) or "—"),
        ("Data de aplicação", _clean(patient.get("application_date")) or "—"),
        ("Sexo", _clean(patient.get("sex")) or "—"),
        ("Escolaridade", _clean(patient.get("education")) or "—"),
        ("Instrumentos aplicados", ", ".join(t for t in (tests or []) if t) or "—"),
        ("Data de emissão", date.today().strftime("%d/%m/%Y")),
    ]
    table = doc.add_table(rows=len(meta_rows), cols=2)
    table.style = "Table Grid"
    table.autofit = True
    for (label, value), row in zip(meta_rows, table.rows):
        c0, c1 = row.cells
        c0.text = ""
        run = c0.paragraphs[0].add_run(label)
        run.bold = True
        run.font.size = Pt(10)
        c1.text = ""
        c1.paragraphs[0].add_run(value).font.size = Pt(10)

    doc.add_paragraph()

    for key, label in SECTION_ORDER:
        if key not in (report or {}):
            continue
        value = report[key]
        _heading(doc, label)
        if key == "resultados_por_dominio":
            _domain_block(doc, value)
        elif isinstance(value, list):
            _bullets(doc, value)
        else:
            _body(doc, value)

    # Assinatura + aviso
    doc.add_paragraph()
    doc.add_paragraph()
    sign = doc.add_paragraph("__________________________________________")
    sign.paragraph_format.space_after = Pt(2)
    cap = doc.add_paragraph()
    cr = cap.add_run("Profissional responsável — assinatura e registro")
    cr.font.size = Pt(9)
    cr.font.color.rgb = MUTED

    disc = doc.add_paragraph()
    dr = disc.add_run(
        "Documento gerado pelo NeuroScore com apoio de inteligência artificial. "
        "O conteúdo exige revisão, validação clínica e assinatura de profissional "
        "habilitado antes de qualquer uso."
    )
    dr.italic = True
    dr.font.size = Pt(8)
    dr.font.color.rgb = MUTED

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
