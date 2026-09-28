/* NeuroScore — aba "Geração de Laudo Neuropsicológico".
   Formulário + upload dos testes já corrigidos → /api/ai/laudo-neuro → laudo nas
   14 seções (server/laudo_neuro_spec.json) → .docx ou impressão/PDF.
   Usa os helpers globais de app.js: api, toast, esc, state, svgToPng. */
(function () {
  const $ = (s) => document.querySelector(s);
  const AUSENTE = 'Dado não fornecido para esta avaliação.';
  let files = [];
  let laudo = null;

  // ---------- formulário ----------
  function today() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }
  function fmtDate(iso) { return iso ? iso.split('-').reverse().join('/') : ''; }
  function calcAge() {
    const b = $('#gl_nasc').value, ref = $('#gl_data').value || today();
    if (!b) return;
    const [by, bm, bd] = b.split('-').map(Number), [ry, rm, rd] = ref.split('-').map(Number);
    let y = ry - by, m = rm - bm;
    if (rd < bd) m--;
    if (m < 0) { y--; m += 12; }
    if (y >= 0) $('#gl_idade').value = `${y} anos e ${m} ${m === 1 ? 'mês' : 'meses'}`;
    if (!$('#gl_faixa').value && y >= 0) $('#gl_faixa').value = y >= 18 ? 'Adulto' : y >= 12 ? 'Adolescente' : 'Criança';
  }
  $('#gl_nasc').addEventListener('change', calcAge);
  $('#gl_data').addEventListener('change', calcAge);
  $('#gl_nome').addEventListener('change', () => {
    const nm = $('#gl_nome').value.trim().toLowerCase();
    const p = (state.patients || []).find((x) => (x.name || '').trim().toLowerCase() === nm);
    if (!p) return;
    if (p.birth_date && !$('#gl_nasc').value) $('#gl_nasc').value = p.birth_date;
    if (p.sex && !$('#gl_sexo').value) $('#gl_sexo').value = p.sex;
    if (p.education && !$('#gl_escol').value) $('#gl_escol').value = p.education;
    calcAge();
  });

  window.glOnShow = function () {
    const p = state.profile || {};
    if (!$('#gl_psi').value && p.full_name) $('#gl_psi').value = p.full_name;
    if (!$('#gl_crp').value && p.professional_id) $('#gl_crp').value = p.professional_id;
    if (!$('#gl_data').value) $('#gl_data').value = today();
  };

  function dados() {
    const v = (id) => $(id).value.trim();
    return {
      faixa_etaria: v('#gl_faixa'),
      identificacao: {
        nome: v('#gl_nome'), sexo: v('#gl_sexo'), data_nascimento: fmtDate(v('#gl_nasc')), idade: v('#gl_idade'),
        escolaridade_ou_profissao: v('#gl_escol'), lateralidade: v('#gl_lat'),
        psicologa_responsavel: v('#gl_psi'), CRP: v('#gl_crp'), solicitante: v('#gl_solic'),
        finalidade: v('#gl_final'), data_laudo: fmtDate(v('#gl_data')),
      },
      queixa_principal: v('#gl_queixa'),
      anamnese: v('#gl_anamnese'),
      observacao_clinica: v('#gl_obs'),
      procedimentos: { numero_sessoes: v('#gl_sessoes'), duracao_sessoes: v('#gl_duracao'), outros: v('#gl_proc') },
      escores_digitados: v('#gl_escores'),
      arquivos_enviados: files.map((f) => f.name),
    };
  }

  // ---------- arquivos ----------
  const OK_EXT = /\.(pdf|jpe?g|png|webp|docx?|xlsx?)$/i;
  function renderFiles() {
    $('#gl_fileList').innerHTML = files.map((f, i) =>
      `<div class="file-pill"><span>${esc(f.name)}</span><small>${(f.size / 1024 / 1024).toFixed(1)} MB</small>` +
      `<button type="button" class="btn ghost xs" data-rm="${i}" title="Remover">×</button></div>`).join('');
  }
  $('#gl_files').addEventListener('change', (e) => {
    for (const f of e.target.files) {
      if (!OK_EXT.test(f.name)) { toast(`${f.name}: formato não aceito.`, true); continue; }
      if (f.size > 25 * 1024 * 1024) { toast(`${f.name}: acima de 25 MB.`, true); continue; }
      if (!files.some((x) => x.name === f.name && x.size === f.size)) files.push(f);
    }
    e.target.value = '';
    renderFiles();
  });
  $('#gl_fileList').addEventListener('click', (e) => {
    const i = e.target.dataset.rm;
    if (i === undefined) return;
    files.splice(+i, 1);
    renderFiles();
  });

  // ---------- gráfico (barras horizontais) ----------
  function chartSvg(g) {
    const labels = (g && g.rotulos) || [], vals = (g && g.valores) || [];
    const n = Math.min(labels.length, vals.length);
    if (!n) return '';
    const max = g.valor_maximo > 0 ? g.valor_maximo : Math.max(...vals.slice(0, n)) * 1.15 || 1;
    const W = 680, L = 190, R = 60, row = 30, top = 40, H = top + n * row + 16;
    let bars = '';
    for (let i = 0; i < n; i++) {
      const w = Math.max(0, Math.min(1, vals[i] / max)) * (W - L - R), y = top + i * row;
      bars += `<text x="${L - 10}" y="${y + 18}" text-anchor="end" font-size="12" fill="#1b2333">${esc(labels[i])}</text>` +
        `<rect x="${L}" y="${y + 5}" width="${w.toFixed(1)}" height="18" rx="3" fill="#2f57b8"/>` +
        `<text x="${L + w + 6}" y="${y + 18}" font-size="12" font-weight="700" fill="#1b2333">${esc(vals[i])}</text>`;
    }
    return `<svg class="chart-svg" viewBox="0 0 ${W} ${H}" role="img">` +
      `<text x="${W / 2}" y="22" text-anchor="middle" font-size="14" font-weight="700" fill="#1b2333">${esc(g.titulo || '')}</text>` +
      `<line x1="${L}" y1="${top}" x2="${L}" y2="${H - 12}" stroke="#c9d1e0"/>${bars}</svg>`;
  }

  // ---------- renderização do laudo ----------
  const IDENT = [['nome_paciente', 'Nome'], ['sexo', 'Sexo'], ['idade', 'Idade'], ['data_nascimento', 'Data de nascimento'],
    ['escolaridade_ou_profissao', 'Escolaridade / Profissão'], ['lateralidade', 'Lateralidade'],
    ['psicologa_responsavel', 'Psicóloga responsável'], ['crp', 'CRP'], ['solicitante', 'Solicitante'],
    ['finalidade', 'Finalidade'], ['data_laudo', 'Data do laudo']];
  const para = (t) => esc(t || AUSENTE).split(/\n+/).filter(Boolean).map((x) => `<p>${x}</p>`).join('');
  const table = (cols, rows) => (cols && cols.length && rows && rows.length)
    ? `<table class="gl-table"><thead><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>` +
      rows.map((r) => `<tr>${cols.map((_, j) => `<td>${esc(r[j] ?? '')}</td>`).join('')}</tr>`).join('') + '</tbody></table>'
    : '';
  const list = (items) => (items && items.length) ? `<ul>${items.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : '';

  function laudoHtml(l) {
    const id = l.identificacao || {}, imp = l.impressao_diagnostica || {}, rec = l.recomendacoes || {};
    const h = (n, t) => `<h3>${n}. ${t}</h3>`;
    let s = `<h2 class="gl-title">LAUDO PSICOLÓGICO DE AVALIAÇÃO NEUROPSICOLÓGICA</h2>`;
    s += h(1, 'Identificação') + table(['Campo', 'Informação'], IDENT.map(([k, t]) => [t, id[k] || AUSENTE]));
    s += h(2, 'Descrição da demanda') + para(l.descricao_demanda);
    s += h(3, 'Procedimentos realizados') + para(l.procedimentos_realizados);
    s += h(4, 'Instrumentos utilizados') + (table(['Instrumento', 'Categoria', 'O que avalia'],
      (l.instrumentos_utilizados || []).map((i) => [i.nome, i.categoria, i.o_que_avalia])) || para(''));
    s += h(5, 'Referencial teórico') + para(l.referencial_teorico);
    s += h(6, 'Análise da anamnese') + para(l.analise_anamnese);
    s += h(7, 'Observação clínica') + para(l.observacao_clinica);
    s += h(8, 'Análise e interpretação dos testes');
    const testes = l.analise_testes || [];
    if (!testes.length) s += para('');
    for (const t of testes) {
      s += `<h4>${esc(t.instrumento)}</h4><h5>O que o teste avalia</h5>${para(t.o_que_o_teste_avalia)}`;
      s += table((t.tabela || {}).colunas, (t.tabela || {}).linhas);
      const svg = chartSvg(t.grafico);
      if (svg) s += `<div class="gl-chart">${svg}</div>`;
      for (const [k, lab] of [['resultados_obtidos', 'Resultados obtidos'], ['classificacao_normativa', 'Classificação normativa'],
        ['impacto_funcional', 'Impacto funcional'], ['integracao_clinica', 'Integração clínica']]) {
        if (t[k]) s += `<h5>${lab}</h5>${para(t[k])}`;
      }
    }
    s += h(9, 'Integração neuropsicológica') + para(l.integracao_neuropsicologica);
    s += h(10, 'Impressão diagnóstica') + para(imp.texto) + table(['Hipótese', 'DSM-5-TR', 'CID-10', 'Fundamentação'],
      (imp.hipoteses || []).map((x) => [x.nome, x.codigo_dsm, x.codigo_cid, x.fundamentacao]));
    s += h(11, 'Conclusão') + para(l.conclusao);
    s += h(12, 'Recomendações');
    for (const [k, lab] of [['escolares', 'Escolares'], ['familia', 'Família'], ['equipe_multidisciplinar', 'Equipe multidisciplinar']]) {
      if ((rec[k] || []).length) s += `<h5>${lab}</h5>${list(rec[k])}`;
    }
    s += h(13, 'Parecer técnico') + para(l.parecer_tecnico);
    s += h(14, 'Observação ética final') + para(l.observacao_etica_final);
    s += `<div class="gl-sign"><div>__________________________________________</div>` +
      `<strong>${esc(id.psicologa_responsavel || '')}</strong>${id.crp ? `<div>CRP ${esc(id.crp)}</div>` : ''}</div>`;
    return s;
  }

  function showLaudo() {
    $('#gl_resultCard').hidden = false;
    $('#gl_doc').innerHTML = laudoHtml(laudo);
    const al = laudo.alertas_para_revisao || [];
    $('#gl_alertas').hidden = !al.length;
    $('#gl_alertas').innerHTML = al.length ? `<div><b>Para revisar antes de assinar:</b>${list(al)}</div>` : '';
    $('#gl_resultCard').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // ---------- gerar ----------
  $('#gl_gerar').addEventListener('click', async () => {
    if (!files.length && !$('#gl_escores').value.trim()) { toast('Envie os arquivos dos testes (ou digite os escores).', true); return; }
    if (!$('#gl_nome').value.trim()) { toast('Informe o nome do paciente.', true); return; }
    const btn = $('#gl_gerar'), orig = btn.textContent, t0 = Date.now();
    btn.disabled = true;
    const tick = setInterval(() => { btn.textContent = `Gerando laudo… ${Math.round((Date.now() - t0) / 1000)}s`; }, 1000);
    try {
      const fd = new FormData();
      fd.append('dados_json', JSON.stringify(dados()));
      files.forEach((f) => fd.append('files', f));
      laudo = await api('/api/ai/laudo-neuro', { method: 'POST', body: fd });
      showLaudo();
      toast('Laudo neuropsicológico gerado.');
      try { window.afterLaudo && window.afterLaudo(); } catch {}
    } catch (e) {
      toast(e.message, true);
      if (/cr[eé]dito/i.test(e.message || '') && window.showView) window.showView('planos');
    } finally { clearInterval(tick); btn.disabled = false; btn.textContent = orig; }
  });

  // ---------- .docx ----------
  $('#gl_docx').addEventListener('click', async () => {
    if (!laudo) return;
    const btn = $('#gl_docx'), orig = btn.textContent;
    btn.disabled = true; btn.textContent = 'Gerando…';
    try {
      const charts = [];
      for (const t of laudo.analise_testes || []) {
        const svg = chartSvg(t.grafico);
        if (!svg) continue;
        const png = await svgToPng(svg);
        if (png) charts.push({ test: t.instrumento, title: (t.grafico || {}).titulo || '', image: png });
      }
      const h = { 'Content-Type': 'application/json' };
      if (state.token) h.Authorization = `Bearer ${state.token}`;
      const r = await fetch('/api/laudo/neuro-docx', { method: 'POST', headers: h, body: JSON.stringify({ laudo, charts }) });
      if (!r.ok) { let d; try { d = await r.json(); } catch { d = { detail: await r.text() }; } throw new Error(d.detail || `HTTP ${r.status}`); }
      const blob = await r.blob(), m = (r.headers.get('Content-Disposition') || '').match(/filename="?([^"]+)"?/);
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = m ? m[1] : 'laudo_neuropsicologico.docx';
      a.click(); URL.revokeObjectURL(a.href);
      toast('Laudo salvo em .docx.');
    } catch (e) { toast(e.message, true); } finally { btn.disabled = false; btn.textContent = orig; }
  });

  // ---------- imprimir / PDF ----------
  $('#gl_print').addEventListener('click', () => {
    if (!laudo) return;
    const w = window.open('', '_blank');
    if (!w) { toast('Permita pop-ups para imprimir.', true); return; }
    w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>Laudo Neuropsicológico</title><style>
      body{font-family:'Times New Roman',Times,serif;font-size:12pt;color:#1b2333;margin:2cm;line-height:1.45}
      p{text-align:justify;margin:0 0 8px} h2{text-align:center;font-size:15pt} h3{color:#2f57b8;text-transform:uppercase;font-size:12pt;margin:18px 0 6px}
      h4{color:#2f57b8;font-size:11.5pt;margin:14px 0 4px} h5{font-size:11pt;margin:8px 0 2px}
      table{border-collapse:collapse;width:100%;margin:6px 0 10px;font-size:10pt} th,td{border:1px solid #8a93a6;padding:4px 6px;text-align:left} th{background:#eef2f9}
      .gl-chart svg{width:100%;max-width:640px} .gl-sign{text-align:center;margin-top:60px}
      @page{margin:2cm} body{margin:0}</style></head><body>${laudoHtml(laudo)}</body></html>`);
    w.document.close(); w.focus();
    setTimeout(() => { try { w.print(); } catch {} }, 400);
  });
})();
