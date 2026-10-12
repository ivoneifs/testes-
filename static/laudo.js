/* NeuroScore — aba "Geração de Laudo Neuropsicológico".
   Formulário + upload dos testes já corrigidos → /api/ai/laudo-neuro → laudo nas
   14 seções (server/laudo_neuro_spec.json) → .docx ou impressão/PDF.
   Usa os helpers globais de app.js: api, toast, esc, state, svgToPng. */
(function () {
  const $ = (s) => document.querySelector(s);
  const AUSENTE = 'Dado não fornecido para esta avaliação.';
  let files = [];
  let anamFiles = [];
  let laudo = null;

  // ---------- formulário ----------
  function today() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }
  function fmtDate(iso) { return iso ? iso.split('-').reverse().join('/') : ''; }
  function calcAge() {
    const b = $('#gl_nasc').value, ref = $('#gl_aplic').value || $('#gl_data').value || today();
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
  $('#gl_aplic').addEventListener('change', calcAge);
  // dados do cadastro do paciente (inclui identificação e respostas da anamnese preenchida)
  const setIf = (id, v) => { if (v && !$(id).value) $(id).value = v; };
  function fillFromPatient(p) {
    const d = p.dados || {}, a = (p.anamnese || {}).respostas || {};
    setIf('#gl_nome', p.name); setIf('#gl_nasc', p.birth_date); setIf('#gl_sexo', p.sex || d.sexo); setIf('#gl_escol', p.education);
    setIf('#gl_lat', d.lateralidade); setIf('#gl_cpf', d.cpf); setIf('#gl_mae', d.mae); setIf('#gl_pai', d.pai); setIf('#gl_cidade', d.cidade);
    setIf('#gl_solic', [d.solicitante, d.especialidade].filter(Boolean).join(' – '));
    if (a.medicacao === 'Não') setIf('#gl_meds', 'Nenhuma.');
    else if (a.medicacao === 'Sim') setIf('#gl_meds', a.medicacao_qual || 'Faz uso de medicação (não especificada).');
    const fam = [['fam_alcoolismo', 'alcoolismo'], ['fam_def_mental', 'deficiência mental'], ['fam_psiq', 'tratamento psiquiátrico']]
      .filter(([k]) => (a[k] || []).length).map(([k, t]) => `${t} (${a[k].join(' e ').toLowerCase()})`);
    if (fam.length) setIf('#gl_famhist', 'Há casos na família de ' + fam.join('; ') + '.');
    calcAge();
  }
  // História de Vida + testes já corrigidos e salvos (aba Testes realizados) deste paciente
  let saved = [], sel = new Set();
  const pkey = (name, birth) => (String(name || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().split(/\s+/).filter(Boolean).join(' ') || 'sem-nome') + '|' + (birth || '');
  async function loadSaved(preselect) {
    const name = $('#gl_nome').value.trim();
    if (!name) { saved = []; renderSaved(); return; }
    try {
      const { results = [] } = await api('/api/test-results');
      const key = pkey(name, $('#gl_nasc').value), nm = key.split('|')[0];
      saved = results.filter(r => r.patient_key === key || (!$('#gl_nasc').value && r.patient_key.split('|')[0] === nm));
      sel = new Set(preselect || saved.map(r => r.id));
    } catch { saved = []; }
    renderSaved();
  }
  function renderSaved() {
    $('#gl_savedCard').hidden = !saved.length;
    const HV = 'História de Vida';
    const ord = [...saved].sort((a, b) => (b.test === HV) - (a.test === HV));
    $('#gl_saved').innerHTML = ord.map(r => `<label class="gl-saved-item${sel.has(r.id) ? ' on' : ''}">
      <input type="checkbox" data-gl-saved="${r.id}"${sel.has(r.id) ? ' checked' : ''}>
      <span>${r.test === HV ? '📇 ' : '🧪 '}<b>${esc(window.NS?.testLabel ? window.NS.testLabel(r.test) : r.test)}</b><small>${new Date(r.updated_at).toLocaleDateString('pt-BR')}</small></span></label>`).join('');
  }
  $('#gl_saved').addEventListener('change', (e) => {
    const c = e.target.closest('[data-gl-saved]'); if (!c) return;
    c.checked ? sel.add(c.dataset.glSaved) : sel.delete(c.dataset.glSaved); renderSaved();
  });
  async function onPatientChange() {
    const nm = $('#gl_nome').value.trim().toLowerCase();
    const p = (state.patients || []).find((x) => (x.name || '').trim().toLowerCase() === nm);
    if (p) fillFromPatient(p);
    calcAge();
    loadSaved();
  }
  $('#gl_nome').addEventListener('change', onPatientChange);
  $('#gl_nasc').addEventListener('change', () => loadSaved());
  // chamado pela aba Testes realizados: laudo completo (todos os marcados) ou de teste isolado
  window.NS = window.NS || {};
  window.NS.glFromSaved = async function (recs, tipo) {
    const p0 = recs[0]?.patient || {};
    ['#gl_nome', '#gl_nasc', '#gl_sexo', '#gl_escol', '#gl_lat', '#gl_cpf', '#gl_mae', '#gl_pai', '#gl_cidade', '#gl_solic', '#gl_meds', '#gl_famhist']
      .forEach(id => { $(id).value = ''; });
    $('#gl_nome').value = p0.name || ''; $('#gl_nasc').value = p0.birth_date || '';
    if (p0.sex) $('#gl_sexo').value = p0.sex;
    if (p0.application_date) $('#gl_aplic').value = p0.application_date;
    try { state.patients = (await api('/api/patients')).patients || state.patients; } catch {}
    const pat = (state.patients || []).find(x => x.id === recs[0]?.patient_id) ||
      (state.patients || []).find(x => (x.name || '').trim().toLowerCase() === (p0.name || '').trim().toLowerCase());
    if (pat) fillFromPatient(pat);
    calcAge();
    await loadSaved(recs.map(r => r.id));
    const radio = document.querySelector(`[name="gl_tipo"][value="${tipo === 'teste_isolado' ? 'teste_isolado' : 'completo'}"]`);
    if (radio) radio.checked = true;
    window.glOnShow && window.glOnShow();
    $('#gl_savedCard').scrollIntoView({ behavior: 'smooth', block: 'start' });
    toast('Confira a identificação e clique em "Gerar Laudo Neuropsicológico".');
  };

  // Q-Plataforma (Pearson): atalho + lista dos testes reconhecidos nos relatórios
  let qpTests = null;
  function renderQp() {
    const q = ($('#qpSearch').value || '').toLowerCase();
    $('#qpList').innerHTML = (qpTests || []).filter(t => !q || t.nome.toLowerCase().includes(q)).map(t =>
      `<li><span>${esc(t.nome)}</span>${t.nativo ? '<span class="qp-tag qp-tag--nat">NeuroScore</span>' : '<span class="qp-tag">PDF da Pearson</span>'}</li>`
    ).join('') || '<li class="muted">Nenhum teste encontrado.</li>';
  }
  async function loadQp() {
    if (qpTests) return;
    try {
      const { url, tests } = await api('/api/qplataforma');
      qpTests = tests; $('#qpOpen').href = url; $('#qpCount').textContent = tests.length; renderQp();
    } catch {}
  }
  $('#qpSearch')?.addEventListener('input', renderQp);

  window.glOnShow = function () {
    loadQp();
    const p = state.profile || {};
    if (!$('#gl_psi').value && p.full_name) $('#gl_psi').value = p.full_name;
    if (!$('#gl_crp').value && p.professional_id) $('#gl_crp').value = p.professional_id;
    if (!$('#gl_data').value) $('#gl_data').value = today();
    if (!$('#gl_aplic').value) $('#gl_aplic').value = today();
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
      cpf: v('#gl_cpf'), filiacao: { mae: v('#gl_mae'), pai: v('#gl_pai') }, cidade: v('#gl_cidade'),
      historico_familiar_transtornos: v('#gl_famhist'), medicacoes_em_uso: v('#gl_meds'),
      testes_realizados_ids: saved.filter(r => sel.has(r.id)).map(r => r.id),
      patient_id: ((state.patients || []).find(x => (x.name || '').trim().toLowerCase() === v('#gl_nome').toLowerCase()) || {}).id || null,
      tipo_laudo: (document.querySelector('[name="gl_tipo"]:checked') || {}).value || 'completo',
      data_aplicacao: fmtDate(v('#gl_aplic')),
      arquivos_enviados: files.map((f) => f.name),
      anamnese_arquivos: anamFiles.map((f) => f.name),
      // para o motor de correção (normas por idade), datas em ISO
      paciente_motor: { name: v('#gl_nome'), birth_date: v('#gl_nasc'), application_date: v('#gl_aplic') || v('#gl_data'),
        sex: v('#gl_sexo'), education: v('#gl_escol') },
    };
  }

  // ---------- arquivos ----------
  const OK_EXT = /\.(pdf|jpe?g|png|webp|docx?|xlsx?)$/i;
  const pills = (arr) => arr.map((f, i) =>
      `<div class="file-pill"><span>${esc(f.name)}</span><small>${(f.size / 1024 / 1024).toFixed(1)} MB</small>` +
      `<button type="button" class="btn ghost xs" data-rm="${i}" title="Remover">×</button></div>`).join('');
  function renderFiles() {
    $('#gl_fileList').innerHTML = pills(files);
    $('#gl_anamList').innerHTML = pills(anamFiles);
  }
  function addFiles(arr, input, re) {
    for (const f of input.files) {
      if (!re.test(f.name)) { toast(`${f.name}: formato não aceito.`, true); continue; }
      if (f.size > 25 * 1024 * 1024) { toast(`${f.name}: acima de 25 MB.`, true); continue; }
      if (!arr.some((x) => x.name === f.name && x.size === f.size)) arr.push(f);
    }
    input.value = '';
    renderFiles();
  }
  $('#gl_files').addEventListener('change', (e) => addFiles(files, e.target, OK_EXT));
  $('#gl_anamFiles').addEventListener('change', (e) => addFiles(anamFiles, e.target, /\.(pdf|jpe?g|png|webp|docx?)$/i));
  for (const [id, arr] of [['#gl_fileList', files], ['#gl_anamList', anamFiles]]) {
    $(id).addEventListener('click', (e) => {
      const i = e.target.dataset.rm;
      if (i === undefined) return;
      arr.splice(+i, 1);
      renderFiles();
    });
  }

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

  // ---------- renderização do laudo (modelo da profissional — server/laudo_modelo.py) ----------
  const para = (t) => esc(t || AUSENTE).split(/\n+/).filter(Boolean).map((x) => `<p>${x}</p>`).join('');
  const table = (cols, rows) => (cols && cols.length && rows && rows.length)
    ? `<table class="gl-table"><thead><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>` +
      rows.map((r) => `<tr>${cols.map((_, j) => `<td>${esc(r[j] ?? '')}</td>`).join('')}</tr>`).join('') + '</tbody></table>'
    : '';
  const list = (items) => (items && items.length) ? `<ul>${items.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : '';
  const line = (pairs) => { const p = pairs.filter(([, v]) => v); return p.length ? `<p class="gl-id">${p.map(([k, v]) => `<b>${k}:</b> ${esc(v)}`).join('&emsp;&emsp;')}</p>` : ''; };

  function laudoHtml(l) {
    const id = l.identificacao || {}, imp = l.impressao_diagnostica || {}, rec = l.recomendacoes || {}, fx = l.textos_fixos || {};
    const h = (t) => `<h3>${t}</h3>`;
    let s = `<h2 class="gl-title">${esc(fx.titulo || 'Laudo Psicológico de Avaliação Neuropsicológica')}</h2>${para(fx.nota_cfp)}`;
    s += h('IDENTIFICAÇÃO:');
    s += line([['Paciente', id.nome_paciente], ['Sexo', id.sexo]]);
    s += line([['Data de nascimento', id.data_nascimento], ['Lateralidade', id.lateralidade], ['Idade na avaliação', id.idade]]);
    s += line([['CPF', id.cpf], ['Escolaridade', id.escolaridade]]);
    s += line([['Filiação', [id.filiacao_mae, id.filiacao_pai].filter(Boolean).join(' / ')]]);
    s += '<br>' + line([['Autora/Psicóloga', [id.psicologa_responsavel, id.crp ? 'CRP ' + id.crp : ''].filter(Boolean).join(' - ')]]);
    s += line([['Solicitante', id.solicitante]]) + line([['Finalidade', id.finalidade || 'Avaliação Neuropsicológica.']]);
    if (id.data_construcao) s += `<p>Laudo construído em ${esc(id.data_construcao)}.</p>`;
    s += h('DESCRIÇÃO DA DEMANDA:') + para(l.descricao_demanda);
    s += h('PROCEDIMENTOS:') + '<p>Os instrumentos utilizados para aquisição de dados foram:</p>' + list(l.procedimentos);
    s += h('TESTES PSICOLÓGICOS E NEUROPSICOLÓGICOS:') + ((l.instrumentos_utilizados || []).map((i, n) =>
      `<p>${n + 1}. ${esc(i.nome)}${i.referencia ? ` (${esc(i.referencia)})` : ''}.${i.objetivo ? ` Objetivo: ${esc(i.objetivo)}` : ''}</p>`).join('') || para(''));
    s += h('REFERENCIAL TEÓRICO METODOLÓGICO:') + para(fx.referencial_teorico);
    s += h('NÚMERO DE ENCONTROS E TEMPO DE DURAÇÃO:') + para(l.numero_encontros);
    s += h('HISTÓRICO FAMILIAR DE TRANSTORNOS MENTAIS:') + para(l.historico_familiar_transtornos);
    s += h('MEDICAÇÕES EM USO:') + para(l.medicacoes_em_uso);
    s += h('ANÁLISE DO INSTRUMENTO E INTERPRETAÇÃO:');
    const testes = l.analise_testes || [];
    if (!testes.length) s += para('');
    for (const t of testes) {
      s += `<p class="gl-test"><b>${esc(t.instrumento)}.</b> ${esc(t.descricao || '')}</p>`;
      for (const tb of t.tabelas || []) s += (tb.titulo ? `<h5>${esc(tb.titulo)}</h5>` : '') + table(tb.colunas, tb.linhas);
      const svg = chartSvg(t.grafico);
      if (svg) s += `<div class="gl-chart">${svg}</div>`;
      if (t.base_conceitual) s += `<h5>Base conceitual teórica:</h5>${para(t.base_conceitual)}`;
      s += `<h5>Interpretação:</h5>${para(t.interpretacao)}`;
    }
    s += h('CONCLUSÃO E SÍNTESE') + para(l.conclusao_sintese);
    s += h('Impressão diagnóstica:') + para(imp.texto) + table(['Hipótese', 'DSM-5-TR', 'CID', 'Fundamentação'],
      (imp.hipoteses || []).map((x) => [x.nome, x.codigo_dsm, x.codigo_cid, x.fundamentacao]));
    s += h('Obs.: Importante:') + list([fx.obs_importante].filter(Boolean));
    s += h('SUGESTÕES DE ENCAMINHAMENTOS:') + (list(l.sugestoes_encaminhamentos) || para(''));
    if ((rec.familia || []).length || (rec.escolares || []).length) {
      s += h('RECOMENDAÇÕES:');
      if ((rec.familia || []).length) s += `<h5>Orientações à Família:</h5>${list(rec.familia)}`;
      if ((rec.escolares || []).length) s += `<h5>Orientações Escolares:</h5>${list(rec.escolares)}`;
    }
    s += h('À EQUIPE MULTIDISCIPLINAR:') + (fx.equipe_multidisciplinar || []).map((x) => `<p>${esc(x)}</p>`).join('');
    if (l.local_data) s += `<p class="gl-date">${esc(l.local_data)}</p>`;
    s += `<div class="gl-sign"><div>________________________________________</div>` +
      `<strong>${esc(id.psicologa_responsavel || '')}</strong>${id.crp ? `<div>CRP ${esc(id.crp)}</div>` : ''}</div>`;
    s += `<div class="gl-foot">${(fx.rodape || []).map((x, i) => i ? `<div>${esc(x)}</div>` : `<b>${esc(x)}</b>`).join('')}</div>`;
    return s;
  }

  function showLaudo() {
    $('#gl_resultCard').hidden = false;
    $('#gl_doc').innerHTML = laudoHtml(laudo);
    const al = laudo.alertas_para_revisao || [];
    const cc = laudo.correcao_automatica || [];
    $('#gl_corrigidos').hidden = !cc.length;
    $('#gl_corrigidos').innerHTML = cc.length ? `<div><b>Corrigidos pelo NeuroScore (normas das planilhas):</b> ${cc.map((c) => esc(c.teste)).join(', ')}</div>` : '';
    $('#gl_alertas').hidden = !al.length;
    $('#gl_alertas').innerHTML = al.length ? `<div><b>Para revisar antes de assinar:</b>${list(al)}</div>` : '';
    $('#gl_resultCard').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // ---------- gerar ----------
  $('#gl_gerar').addEventListener('click', async () => {
    const nSel = saved.filter(r => sel.has(r.id) && r.test !== 'História de Vida').length;
    if (!files.length && !nSel && !$('#gl_escores').value.trim()) { toast('Envie os arquivos dos testes, marque testes realizados ou digite os escores.', true); return; }
    if (!$('#gl_nome').value.trim()) { toast('Informe o nome do paciente.', true); return; }
    const btn = $('#gl_gerar'), orig = btn.textContent, t0 = Date.now();
    btn.disabled = true;
    const tick = setInterval(() => { btn.textContent = `Corrigindo e gerando laudo… ${Math.round((Date.now() - t0) / 1000)}s`; }, 1000);
    try {
      const fd = new FormData();
      fd.append('dados_json', JSON.stringify(dados()));
      files.forEach((f) => fd.append('files', f));
      anamFiles.forEach((f) => fd.append('anamnese_files', f));
      laudo = await api('/api/ai/laudo-neuro', { method: 'POST', body: fd });
      showLaudo();
      const novos = laudo.salvos_em_testes_realizados || [];
      toast(novos.length ? `Laudo gerado. Salvos em Testes realizados: ${novos.join(', ')}.` : 'Laudo neuropsicológico gerado.');
      if (novos.length) {
        const keep = new Set(sel);
        anamFiles.length = 0; files.length = 0; renderFiles();   // já estão salvos; não reenviar
        await loadSaved(); saved.forEach(r => { if (keep.has(r.id) || novos.includes(r.test)) sel.add(r.id); }); renderSaved();
      }
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
      body{font-family:'Times New Roman',Times,serif;font-size:12pt;color:#000;line-height:1.5;margin:0}
      p{text-align:justify;margin:0 0 8px} h2{text-align:center;font-size:14pt;margin:0 0 12px} h3{font-size:12pt;margin:18px 0 6px;page-break-after:avoid}
      h5{font-size:12pt;margin:10px 0 4px} .gl-id{text-align:left;margin:0 0 2px} ul{margin:0 0 8px 18px;padding:0} li{text-align:justify;margin-bottom:4px}
      table{border-collapse:collapse;width:100%;margin:6px 0 10px;font-size:11pt} th,td{border:1px solid #000;padding:3px 6px;text-align:left} th{background:#f2f2f2}
      .gl-chart svg{width:100%;max-width:600px} .gl-date{text-align:right;margin-top:16px} .gl-sign{text-align:center;margin-top:60px}
      .gl-foot{margin-top:40px;font-size:10pt} @page{margin:2.5cm 3cm}</style></head><body>${laudoHtml(laudo)}</body></html>`);
    w.document.close(); w.focus();
    setTimeout(() => { try { w.print(); } catch {} }, 400);
  });
})();
