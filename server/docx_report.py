"""Geração do laudo neuropsicológico integrado em .docx (Word).

Usa apenas os dados já produzidos pelo fluxo (paciente + resultado estruturado da
IA + testes corrigidos). Não chama serviços externos. O texto continua exigindo
revisão e assinatura de profissional habilitado.
"""
from __future__ import annotations

import base64
import io
from datetime import date
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

INK = RGBColor(0x1B, 0x23, 0x33)
ACCENT = RGBColor(0x2F, 0x57, 0xB8)
MUTED = RGBColor(0x60, 0x6A, 0x80)

SECTION_ORDER = [
    ("identificacao_e_demanda", "Identificação e demanda"),
    ("historia_clinica_e_desenvolvimental", "História clínica e desenvolvimental"),
    ("procedimentos_e_instrumentos", "Procedimentos e instrumentos"),
    ("analise_instrumentos", "Análise de instrumentos e interpretações"),
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
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.font.color.rgb = INK
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    # Corpo de texto justificado (List Bullet herda de Normal, mas fixa explicitamente).
    for style_name in ("List Bullet",):
        try:
            doc.styles[style_name].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        except KeyError:
            pass


def _heading(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(4)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text.upper())
    run.bold = True
    run.font.size = Pt(12)
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


def _data_table(doc: Document, columns: list, rows: list, size: float = 9) -> None:
    columns = [_clean(c) for c in (columns or []) if _clean(c)]
    rows = [r for r in (rows or []) if isinstance(r, list)]
    if not columns or not rows:
        return
    table = doc.add_table(rows=1 + len(rows), cols=len(columns))
    table.style = "Table Grid"
    for j, name in enumerate(columns):
        run = table.rows[0].cells[j].paragraphs[0].add_run(name)
        run.bold = True
        run.font.size = Pt(size)
    for i, row in enumerate(rows, start=1):
        for j in range(len(columns)):
            val = _clean(row[j]) if j < len(row) else ""
            table.rows[i].cells[j].paragraphs[0].add_run(val).font.size = Pt(size)
    doc.add_paragraph()


def _instrument_analysis(doc: Document, entries: list) -> None:
    for entry in entries or []:
        if not isinstance(entry, dict):
            _body(doc, entry)
            continue
        name = _clean(entry.get("instrumento"))
        if name:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(8)
            r = p.add_run(name)
            r.bold = True
            r.font.size = Pt(10.5)
        _body(doc, entry.get("objetivo"))
        for tbl in entry.get("tabelas") or []:
            if not isinstance(tbl, dict):
                continue
            title = _clean(tbl.get("titulo"))
            if title:
                tp = doc.add_paragraph()
                tp.paragraph_format.space_before = Pt(4)
                tr = tp.add_run(title)
                tr.italic = True
                tr.font.size = Pt(9.5)
            _data_table(doc, tbl.get("colunas"), tbl.get("linhas"))
        _body(doc, entry.get("comentario"))


def _charts_section(doc: Document, charts: list) -> None:
    """Embute os gráficos (PNG data URL) enviados pelo frontend, um por teste."""
    ok = False
    for c in charts or []:
        img = _clean(c.get("image"))
        if not img.startswith("data:image"):
            continue
        try:
            data = base64.b64decode(img.split(",", 1)[1])
        except Exception:
            continue
        cap = doc.add_paragraph()
        cap.paragraph_format.space_before = Pt(6)
        cr = cap.add_run(" — ".join(x for x in (_clean(c.get("test")), _clean(c.get("title"))) if x))
        cr.italic = True
        cr.font.size = Pt(9.5)
        try:
            doc.add_picture(io.BytesIO(data), width=Inches(5.9))
        except Exception:
            continue
        ok = True
    return ok


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


def build_integrated_docx(patient: dict, report: dict, tests: list[str] | None = None,
                          charts: list | None = None) -> bytes:
    doc = Document()
    _style(doc)

    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Pt(64)
    sec.top_margin = sec.bottom_margin = Pt(56)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tr = title.add_run("AVALIAÇÃO NEUROPSICOLÓGICA COMPLETA")
    tr.bold = True
    tr.font.size = Pt(17)
    tr.font.color.rgb = INK
    title.paragraph_format.space_after = Pt(14)

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
        if key == "analise_instrumentos":
            _instrument_analysis(doc, value)
            if charts:
                _heading(doc, "Gráficos por teste")
                _charts_section(doc, charts)
        elif key == "resultados_por_dominio":
            _domain_block(doc, value)
        elif isinstance(value, list):
            _bullets(doc, value)
        else:
            _body(doc, value)

    if charts and "analise_instrumentos" not in (report or {}):
        _heading(doc, "Gráficos por teste")
        _charts_section(doc, charts)

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


# ---------------- Laudo Neuropsicológico (aba "Geração de Laudo") ----------------
AUSENTE = "Dado não fornecido para esta avaliação."

IDENT_LABELS = [
    ("nome_paciente", "Nome"), ("sexo", "Sexo"), ("idade", "Idade"),
    ("data_nascimento", "Data de nascimento"), ("escolaridade_ou_profissao", "Escolaridade / Profissão"),
    ("lateralidade", "Lateralidade"), ("psicologa_responsavel", "Psicóloga responsável"), ("crp", "CRP"),
    ("solicitante", "Solicitante"), ("finalidade", "Finalidade"), ("data_laudo", "Data do laudo"),
]


def _kv_table(doc: Document, rows: list) -> None:
    table = doc.add_table(rows=len(rows), cols=2)
    table.style = "Table Grid"
    for (label, value), row in zip(rows, table.rows):
        c0, c1 = row.cells
        r = c0.paragraphs[0].add_run(label)
        r.bold = True
        r.font.size = Pt(10)
        c1.paragraphs[0].add_run(_clean(value) or AUSENTE).font.size = Pt(10)
    doc.add_paragraph()


def _sub(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(11)


def _chart_for(doc: Document, charts: list, instrumento: str) -> None:
    for c in charts or []:
        if _clean(c.get("test")) == instrumento:
            _charts_section(doc, [c])


def _h(doc: Document, text: str, size: float = 12, center: bool = False, before: float = 14) -> None:
    """Título de seção do modelo: negrito, preto, Times 12."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(size)


def _label_line(doc: Document, pairs: list) -> None:
    """Linha de identificação: "Rótulo: valor   Rótulo: valor" (rótulo em negrito)."""
    pairs = [(k, _clean(v)) for k, v in pairs if _clean(v)]
    if not pairs:
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_after = Pt(2)
    for i, (k, v) in enumerate(pairs):
        if i:
            p.add_run("      ")
        p.add_run(f"{k}: ").bold = True
        p.add_run(v)


def build_laudo_neuro_docx(laudo: dict, charts: list | None = None) -> bytes:
    """Laudo no modelo da profissional (server/laudo_modelo.py), Times New Roman 12."""
    from . import laudo_modelo
    laudo = laudo or {}
    ident = laudo.get("identificacao") or {}
    fx = laudo.get("textos_fixos") or laudo_modelo.textos_fixos(ident.get("nome_paciente"))
    doc = Document()
    _style(doc)
    for st in ("Normal", "List Bullet", "List Number"):
        try:
            doc.styles[st].font.color.rgb = RGBColor(0, 0, 0)
        except KeyError:
            pass
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Pt(85)   # 3 cm
    sec.top_margin = sec.bottom_margin = Pt(71)   # 2,5 cm

    _h(doc, fx.get("titulo") or laudo_modelo.TITULO, size=14, center=True, before=0)
    _body(doc, fx.get("nota_cfp"))

    _h(doc, "IDENTIFICAÇÃO:")
    _label_line(doc, [("Paciente", ident.get("nome_paciente")), ("Sexo", ident.get("sexo"))])
    _label_line(doc, [("Data de nascimento", ident.get("data_nascimento")), ("Lateralidade", ident.get("lateralidade")),
                      ("Idade na avaliação", ident.get("idade"))])
    _label_line(doc, [("CPF", ident.get("cpf")), ("Escolaridade", ident.get("escolaridade"))])
    fil = [x for x in (_clean(ident.get("filiacao_mae")), _clean(ident.get("filiacao_pai"))) if x]
    if fil:
        _label_line(doc, [("Filiação", " / ".join(fil))])
    doc.add_paragraph()
    _label_line(doc, [("Autora/Psicóloga", " - ".join(x for x in (_clean(ident.get("psicologa_responsavel")),
                                                                  ("CRP " + _clean(ident.get("crp"))) if _clean(ident.get("crp")) else "") if x))])
    _label_line(doc, [("Solicitante", ident.get("solicitante"))])
    _label_line(doc, [("Finalidade", ident.get("finalidade") or "Avaliação Neuropsicológica.")])
    if _clean(ident.get("data_construcao")):
        _body(doc, f"Laudo construído em {_clean(ident.get('data_construcao'))}.")

    _h(doc, "DESCRIÇÃO DA DEMANDA:")
    _body(doc, laudo.get("descricao_demanda") or AUSENTE)

    _h(doc, "PROCEDIMENTOS:")
    _body(doc, "Os instrumentos utilizados para aquisição de dados foram:")
    _bullets(doc, laudo.get("procedimentos") or laudo_modelo.PROCEDIMENTOS_PADRAO)

    instr = [i for i in laudo.get("instrumentos_utilizados") or [] if isinstance(i, dict)]
    _h(doc, "TESTES PSICOLÓGICOS E NEUROPSICOLÓGICOS:")
    if not instr:
        _body(doc, AUSENTE)
    for n, i in enumerate(instr, 1):
        ref = f" ({_clean(i.get('referencia'))})" if _clean(i.get("referencia")) else ""
        obj = f" Objetivo: {_clean(i.get('objetivo'))}" if _clean(i.get("objetivo")) else ""
        _body(doc, f"{n}. {_clean(i.get('nome'))}{ref}.{obj}")

    _h(doc, "REFERENCIAL TEÓRICO METODOLÓGICO:")
    _body(doc, fx.get("referencial_teorico"))
    _h(doc, "NÚMERO DE ENCONTROS E TEMPO DE DURAÇÃO:")
    _body(doc, laudo.get("numero_encontros") or AUSENTE)
    _h(doc, "HISTÓRICO FAMILIAR DE TRANSTORNOS MENTAIS:")
    _body(doc, laudo.get("historico_familiar_transtornos") or AUSENTE)
    _h(doc, "MEDICAÇÕES EM USO:")
    _body(doc, laudo.get("medicacoes_em_uso") or AUSENTE)

    _h(doc, "ANÁLISE DO INSTRUMENTO E INTERPRETAÇÃO:")
    testes = [t for t in laudo.get("analise_testes") or [] if isinstance(t, dict)]
    if not testes:
        _body(doc, AUSENTE)
    for t in testes:
        nome = _clean(t.get("instrumento"))
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.keep_with_next = True
        p.add_run(nome + ". ").bold = True
        p.add_run(_clean(t.get("descricao")))
        for tab in t.get("tabelas") or []:
            if not isinstance(tab, dict):
                continue
            if _clean(tab.get("titulo")):
                _sub(doc, _clean(tab.get("titulo")))
            _data_table(doc, tab.get("colunas"), tab.get("linhas"), size=11)
        _chart_for(doc, charts, nome)
        if _clean(t.get("base_conceitual")):
            _sub(doc, "Base conceitual teórica:")
            _body(doc, t.get("base_conceitual"))
        _sub(doc, "Interpretação:")
        _body(doc, t.get("interpretacao") or AUSENTE)

    _h(doc, "CONCLUSÃO E SÍNTESE")
    _body(doc, laudo.get("conclusao_sintese") or AUSENTE)

    imp = laudo.get("impressao_diagnostica") or {}
    _h(doc, "Impressão diagnóstica:")
    _body(doc, imp.get("texto") or AUSENTE)
    hip = [h for h in imp.get("hipoteses") or [] if isinstance(h, dict)]
    if hip:
        _data_table(doc, ["Hipótese", "DSM-5-TR", "CID", "Fundamentação"],
                    [[h.get("nome"), h.get("codigo_dsm"), h.get("codigo_cid"), h.get("fundamentacao")] for h in hip])

    _h(doc, "Obs.: Importante:")
    _bullets(doc, [fx.get("obs_importante")])

    _h(doc, "SUGESTÕES DE ENCAMINHAMENTOS:")
    _bullets(doc, laudo.get("sugestoes_encaminhamentos") or [AUSENTE])
    rec = laudo.get("recomendacoes") or {}
    if rec.get("familia") or rec.get("escolares"):
        _h(doc, "RECOMENDAÇÕES:")
        if rec.get("familia"):
            _sub(doc, "Orientações à Família:")
            _bullets(doc, rec.get("familia"))
        if rec.get("escolares"):
            _sub(doc, "Orientações Escolares:")
            _bullets(doc, rec.get("escolares"))

    _h(doc, "À EQUIPE MULTIDISCIPLINAR:")
    for t in fx.get("equipe_multidisciplinar") or []:
        _body(doc, t)
    if _clean(laudo.get("local_data")):
        p = doc.add_paragraph(_clean(laudo.get("local_data")))
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    doc.add_paragraph()
    doc.add_paragraph()
    for text, bold in (("_" * 40, False), (_clean(ident.get("psicologa_responsavel")), True),
                       (("CRP " + _clean(ident.get("crp"))) if _clean(ident.get("crp")) else "", False)):
        if not text:
            continue
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        p.add_run(text).bold = bold

    doc.add_paragraph()
    for i, t in enumerate(fx.get("rodape") or []):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(t)
        r.font.size = Pt(10)
        r.bold = i == 0

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
