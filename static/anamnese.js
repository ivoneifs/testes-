/* NeuroScore — História de Vida: anamnese preenchida por MARCAÇÃO (sem escrever).
   Formulário = ficha "Anamnese Infantojuvenil" da profissional. Os dados de identificação
   vêm do cadastro do paciente e voltam para ele (patients.dados); as respostas ficam em
   patients.anamnese e, ao gerar a história, em Testes realizados ("História de Vida").
   Depende de window.NS ({api, toast, esc, state, setPatientFields, applyAnamnesis}). */
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const NS = window.NS || {};
  const esc = (v) => NS.esc ? NS.esc(v) : String(v ?? '');
  const range = (a, b, suf = '') => Array.from({ length: b - a + 1 }, (_, i) => `${a + i}${suf}`);
  const SN = ['Sim', 'Não'];

  // [tipo, id, rótulo, opções]  ·  tipos: multi (várias), one (uma), yn (Sim/Não), sel (lista), txt (opcional), date
  // id começando com "d_" = identificação → salvo no cadastro do paciente (patients.dados)
  const FORM = [
    ['Identificação', [
      ['date', 'd_data_entrevista', 'Data da entrevista'],
      ['one', 'd_sexo', 'Sexo', ['Masculino', 'Feminino']],
      ['one', 'd_lateralidade', 'Lateralidade', ['Destro', 'Canhoto']],
      ['txt', 'd_responsavel', 'Responsável'],
      ['txt', 'd_mae', 'Nome da mãe'],
      ['txt', 'd_pai', 'Nome do pai'],
      ['txt', 'd_cpf', 'CPF'],
      ['txt', 'd_telefone', 'Fone'],
      ['txt', 'd_naturalidade', 'Naturalidade'],
      ['txt', 'd_endereco', 'Endereço'],
      ['txt', 'd_cidade', 'Cidade'],
      ['txt', 'd_solicitante', 'Solicitante'],
      ['txt', 'd_especialidade', 'Especialidade do solicitante'],
      ['txt', 'd_hipotese', 'Hipótese diagnóstica'],
      ['txt', 'd_laudo', 'Laudo'],
    ]],
    ['Motivo da consulta', [
      ['multi', 'motivo', 'Queixas', ['Dificuldade na aprendizagem', 'Dificuldade na atenção/concentração', 'Esquece com facilidade',
        'Não lê', 'Dificuldade em falar', 'Desorganizado', 'Não escreve', 'Não termina suas atividades', 'Agitação motora',
        'Copista', 'Dificuldade em controlar as emoções', 'Não tem medo de nada', 'Evita contato visual',
        'Baixa tolerância à frustração', 'Medo excessivo', 'Contato visual ligeiro', 'Irritabilidade/nervosismo',
        'Seletividade alimentar', 'Estereotipias motoras', 'Não obedece', 'Se incomoda com o barulho', 'Flapping com as mãos',
        'Desafia regras', 'Ansioso', 'Não interage', 'Agressivo físico', 'Agressivo verbal', 'Comportamento infantil para a idade',
        'Coleciona objetos estranhos', 'Procrastinação', "Comunicação literal ('pé da letra')"]],
      ['txt', 'motivo_obs', 'Outras queixas'],
      ['yn', 'medicacao', 'Faz uso de medicação?'],
      ['txt', 'medicacao_qual', 'Qual medicação?'],
    ]],
    ['História gestacional', [
      ['yn', 'planejado', 'Filho(a) planejado(a)?'],
      ['yn', 'adotado', 'Adotado(a)?'],
      ['yn', 'prenatal', 'Fez pré-natal?'],
      ['multi', 'mae_emocional', 'Como a mãe estava emocionalmente?', ['Tranquila', 'Ansiosa', 'Chorosa']],
      ['yn', 'gest_complic', 'Teve complicações na gestação?'],
      ['txt', 'gest_complic_qual', 'Quais complicações na gestação?'],
    ]],
    ['Parto', [
      ['one', 'parto', 'Tipo de parto', ['Cesáreo', 'Normal']],
      ['yn', 'parto_complic', 'Teve complicação no parto?'],
      ['txt', 'parto_complic_qual', 'Qual complicação no parto?'],
      ['sel', 'nasceu_meses', 'Nasceu com quantos meses?', ['6', '7', '8', '9', '10']],
      ['txt', 'tamanho', 'Tamanho ao nascer (cm)'],
      ['txt', 'peso', 'Peso ao nascer'],
    ]],
    ['Desenvolvimento neuropsicomotor', [
      ['sel', 'sentou', 'Sentou (meses)', range(3, 24)],
      ['sel', 'andou_anos', 'Andou (anos)', range(0, 5)],
      ['sel', 'andou_meses', 'Andou (+ meses)', range(0, 11)],
      ['one', 'falou', 'Falou com que idade?', ['Antes de 1 ano', '1 ano', '1 ano e meio', '2 anos', '2 anos e meio', '3 anos', 'Depois dos 3 anos', 'Ainda não fala']],
      ['yn', 'trocas_fala', 'Houve persistência de trocas na fala?'],
      ['sel', 'desfralde_anos', 'Desfralde (anos)', range(0, 8)],
      ['sel', 'desfralde_meses', 'Desfralde (+ meses)', range(0, 11)],
      ['yn', 'enurese_diurna', 'Enurese diurna'],
      ['yn', 'enurese_noturna', 'Enurese noturna'],
      ['yn', 'regressao', 'Regressão'],
    ]],
    ['Alimentação', [
      ['yn', 'mastigacao', 'Tem boa mastigação?'],
      ['yn', 'impulsiv_comer', 'Apresenta impulsividade ao comer?'],
      ['yn', 'seletividade', 'Seletividade alimentar?'],
      ['txt', 'seletividade_obs', 'Seletividade: o que aceita / recusa'],
    ]],
    ['Manipulação e tiques', [
      ['yn', 'morde_labio', 'Morde o lábio?'],
      ['yn', 'arranca_cabelo', 'Quando nervoso arranca cabelos?'],
      ['yn', 'balanca_corpo', 'Balança o corpo?'],
      ['yn', 'morde_colarinho', 'Morde colarinho de blusa?'],
      ['yn', 'roi_unhas', 'Rói unhas?'],
      ['yn', 'cheira_pano', 'Cheira pano?'],
      ['yn', 'bate_cabeca', 'Bate a cabeça na parede?'],
      ['yn', 'mexe_pernas', 'Mexe as pernas quando sentado?'],
    ]],
    ['Sono', [
      ['yn', 'dorme_bem', 'Dorme bem?'],
      ['yn', 'sono_agitado', 'Sono agitado?'],
      ['yn', 'range_dentes', 'Range os dentes?'],
    ]],
    ['Há casos na família de…', [
      ['multi', 'fam_alcoolismo', 'Alcoolismo', ['Família paterna', 'Família materna']],
      ['multi', 'fam_def_mental', 'Deficiência mental', ['Família paterna', 'Família materna']],
      ['multi', 'fam_psiq', 'Tratamento psiquiátrico', ['Família paterna', 'Família materna']],
    ]],
    ['Contexto familiar', [
      ['one', 'pais', 'Pais', ['Casados/amasiados', 'Divorciados']],
      ['one', 'relacao_parental', 'Como é a relação parental?', ['Boa', 'Difícil', 'Não tem contato']],
      ['multi', 'mora_casa', 'Quem mora em casa?', ['Mãe', 'Pai', 'Padrasto', 'Madrasta', 'Irmãos', 'Avós', 'Tios', 'Outros']],
      ['txt', 'mora_casa_obs', 'Moradores (detalhes)'],
    ]],
    ['Sociabilidade', [
      ['multi', 'comp_casa', 'Comportamento em casa', ['Tranquilo', 'Agitado', 'Não para', 'Agressivo', 'Amável']],
      ['multi', 'comp_escola', 'Comportamento na escola', ['Tranquilo', 'Agitado', 'Não para', 'Agressivo', 'Amável']],
      ['one', 'rel_adultos', 'Como se relaciona com adultos', ['Bem', 'Não gosta', 'Agressivo']],
      ['one', 'pref_amigos', 'Prefere amigos', ['Da mesma idade', 'Mais novos', 'Mais velhos', 'De todas as idades']],
      ['yn', 'brinca_grupo', 'Brinca em grupo?'],
      ['yn', 'isola', 'Prefere se isolar?'],
      ['yn', 'obedece', 'Obedece?'],
      ['yn', 'passiva', 'Atitude passiva?'],
      ['yn', 'impositiva', 'Impositiva?'],
      ['yn', 'opositor', 'Opositor?'],
      ['yn', 'dif_amizades', 'Dificuldade em fazer e manter amizades?'],
      ['yn', 'corre_sem_direcao', 'Corre/caminha sem direção?'],
    ]],
    ['Nível de independência (autonomia)', [
      ['yn', 'aut_banho', 'Banho'], ['yn', 'aut_alimentacao', 'Alimentação'], ['yn', 'aut_veste', 'Veste-se'],
      ['yn', 'aut_dentes', 'Escova os dentes'], ['yn', 'aut_sapatos', 'Calça os sapatos'], ['yn', 'aut_penteia', 'Penteia os cabelos'],
      ['yn', 'aut_cadarco', 'Amarra cadarços'], ['yn', 'aut_tesoura', 'Usa tesoura'],
      ['yn', 'aut_machuca', 'Se machuca por falta de atenção'], ['yn', 'aut_perigos', 'Evita perigos'],
      ['yn', 'aut_compras', 'Faz pequenas compras'], ['yn', 'aut_escola', 'Vai à escola'], ['yn', 'aut_recados', 'Dá ou anota recados'],
      ['yn', 'aut_dinheiro', 'Reconhece dinheiro'], ['yn', 'aut_troco', 'Sabe o troco'], ['yn', 'aut_rotina', 'Conhece a própria rotina'],
      ['yn', 'aut_horas', 'Conhece horas e dias da semana'],
      ['one', 'celular', 'Tempo exposto ao celular/telas', ['Menos de 1 h/dia', '1 a 2 h/dia', '2 a 4 h/dia', 'Mais de 4 h/dia']],
      ['txt', 'brincadeira', 'Brincadeira de que mais gosta'],
    ]],
    ['Antecedentes escolares', [
      ['txt', 'escola', 'Nome da escola'],
      ['sel', 'serie', 'Série/ano', ['Educação infantil', '1º ano', '2º ano', '3º ano', '4º ano', '5º ano', '6º ano', '7º ano', '8º ano', '9º ano', '1ª série EM', '2ª série EM', '3ª série EM', 'Não frequenta']],
      ['yn', 'gosta_estudar', 'Gosta de estudar?'],
      ['yn', 'gosta_escola', 'Gosta da escola?'],
      ['multi', 'dif_escola', 'Dificuldades na escola', ['Pedagógica', 'Comportamento']],
      ['yn', 'dif_escrita', 'Dificuldade na escrita?'],
      ['yn', 'dif_calculo', 'Dificuldade no cálculo?'],
      ['yn', 'dif_leitura', 'Dificuldade na leitura?'],
      ['yn', 'organizado', 'Organizado com os materiais escolares?'],
      ['yn', 'dif_esc_pai', 'Pai teve dificuldades escolares?'],
      ['yn', 'dif_esc_mae', 'Mãe teve dificuldades escolares?'],
    ]],
  ];
  const ITEMS = FORM.flatMap(([sec, items]) => items.map(i => ({ sec, type: i[0], id: i[1], label: i[2], opts: i[3] || (i[0] === 'yn' ? SN : null) })));
  const BY_ID = Object.fromEntries(ITEMS.map(i => [i.id, i]));
  let answers = {};

  // ---------- render ----------
  function field(it) {
    const v = answers[it.id];
    if (it.type === 'txt') return `<label class="anam-q anam-txt"><span>${esc(it.label)} <i>(opcional)</i></span><input data-anam="${it.id}" value="${esc(v || '')}" autocomplete="off"></label>`;
    if (it.type === 'date') return `<label class="anam-q anam-txt"><span>${esc(it.label)}</span><input type="date" data-anam="${it.id}" value="${esc(v || '')}"></label>`;
    if (it.type === 'sel') return `<label class="anam-q anam-sel"><span>${esc(it.label)}</span><select data-anam="${it.id}"><option value="">—</option>${it.opts.map(o => `<option${o === v ? ' selected' : ''}>${esc(o)}</option>`).join('')}</select></label>`;
    const on = (o) => it.type === 'multi' ? (v || []).includes(o) : v === o;
    return `<div class="anam-q anam-${it.type}"><span>${esc(it.label)}</span><div class="anam-chips">${it.opts.map(o =>
      `<button type="button" class="anam-chip${on(o) ? ' on' : ''}" data-chip="${it.id}" data-val="${esc(o)}">${esc(o)}</button>`).join('')}</div></div>`;
  }
  function render() {
    const box = $('#anamForm'); if (!box) return;
    box.innerHTML = FORM.map(([sec, items], k) => `<details class="anam-sec"${k < 2 ? ' open' : ''}><summary>${esc(sec)}<span class="anam-count" data-sec-count="${k}"></span></summary>
      <div class="anam-grid">${items.map(i => field(BY_ID[i[1]])).join('')}</div></details>`).join('');
    progress();
  }
  const answered = (id) => { const v = answers[id]; return Array.isArray(v) ? v.length > 0 : !!(v && String(v).trim()); };
  function progress() {
    const marc = ITEMS.filter(i => i.type !== 'txt' && i.type !== 'date');
    $('#anamProg').textContent = `${marc.filter(i => answered(i.id)).length} de ${marc.length} perguntas marcadas`;
    FORM.forEach(([, items], k) => {
      const el = document.querySelector(`[data-sec-count="${k}"]`);
      if (el) { const n = items.filter(i => answered(i[1])).length; el.textContent = n ? ` · ${n}/${items.length}` : ''; }
    });
  }

  // ---------- interação ----------
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-chip]'); if (!b) return;
    const it = BY_ID[b.dataset.chip], val = b.dataset.val;
    if (it.type === 'multi') {
      const cur = new Set(answers[it.id] || []); cur.has(val) ? cur.delete(val) : cur.add(val);
      answers[it.id] = [...cur]; b.classList.toggle('on');
    } else {
      answers[it.id] = answers[it.id] === val ? '' : val;  // clicar de novo desmarca
      b.parentElement.querySelectorAll('.anam-chip').forEach(c => c.classList.toggle('on', c.dataset.val === answers[it.id]));
    }
    progress();
  });
  document.addEventListener('input', (e) => {
    const f = e.target.closest('[data-anam]'); if (!f) return;
    answers[f.dataset.anam] = f.value; progress();
  });

  // ---------- texto legível (vai para a IA e para a "transcrição") ----------
  function idade(birth) {
    if (!birth) return '';
    const b = new Date(birth + 'T00:00'), n = new Date();
    let m = (n.getFullYear() - b.getFullYear()) * 12 + n.getMonth() - b.getMonth(); if (n.getDate() < b.getDate()) m--;
    return m >= 0 ? `${Math.floor(m / 12)} anos e ${m % 12} meses` : '';
  }
  function fmt(it, v) {
    if (it.type === 'date') return String(v).split('-').reverse().join('/');
    return Array.isArray(v) ? v.join('; ') : String(v).trim();
  }
  function toText() {
    const name = $('#hvName').value.trim(), birth = $('#hvBirth').value;
    const out = [`Paciente: ${name || '(sem nome)'}`];
    if (birth) out.push(`Data de nascimento: ${birth.split('-').reverse().join('/')} (idade: ${idade(birth)})`);
    for (const [sec, items] of FORM) {
      const lines = items.map(i => BY_ID[i[1]]).filter(it => answered(it.id)).map(it => `${it.label}: ${fmt(it, answers[it.id])}`);
      if (lines.length) out.push('', `## ${sec}`, ...lines);
    }
    // marcações compostas legíveis
    return out.join('\n');
  }

  // ---------- pacientes ----------
  async function patients(refresh) {
    if (refresh || !NS.state.patients) {
      try { NS.state.patients = (await NS.api('/api/patients')).patients || []; } catch { NS.state.patients = NS.state.patients || []; }
    }
    return NS.state.patients;
  }
  async function fillPick(selId) {
    const sel = $('#hvPick'); if (!sel) return;
    const list = await patients(true);
    const cur = selId ?? sel.value;
    sel.innerHTML = '<option value="">— novo paciente —</option>' + list.map(p =>
      `<option value="${p.id}"${p.id === cur ? ' selected' : ''}>${esc(p.name)}${p.birth_date ? ' · ' + p.birth_date.split('-').reverse().join('/') : ''}</option>`).join('');
  }
  function loadPatient(p) {
    NS.setPatientFields({ name: p.name, birth_date: p.birth_date, sex: p.sex, education: p.education, application_date: $('#applicationDate')?.value });
    answers = { ...((p.anamnese || {}).respostas || {}) };
    for (const [k, v] of Object.entries(p.dados || {})) answers['d_' + k] = v;
    if (p.sex && !answers.d_sexo) answers.d_sexo = p.sex;
    if (p.education && !answers.serie && BY_ID.serie.opts.includes(p.education)) answers.serie = p.education;
    render();
  }
  $('#hvPick')?.addEventListener('change', async (e) => {
    const p = (await patients()).find(x => x.id === e.target.value);
    if (p) { loadPatient(p); NS.toast(`Dados de ${p.name} carregados.`); }
    else { NS.setPatientFields({}); answers = {}; render(); }
  });

  // grava identificação + respostas no cadastro do paciente (cria se não existir)
  async function saveToPatient() {
    const name = $('#hvName').value.trim();
    if (!name) throw new Error('Informe o nome do paciente (ou escolha um paciente cadastrado).');
    const list = await patients();
    const pid = $('#hvPick').value || (list.find(p => (p.name || '').trim().toLowerCase() === name.toLowerCase()) || {}).id;
    const old = list.find(p => p.id === pid) || {};
    const dados = { ...(old.dados || {}) }, respostas = {};
    for (const [k, v] of Object.entries(answers)) {
      if (k.startsWith('d_')) { dados[k.slice(2)] = v; } else if (answered(k)) respostas[k] = v;
    }
    const body = {
      name, birth_date: $('#hvBirth').value || null,
      sex: answers.d_sexo || old.sex || null,
      education: (answers.serie && answers.serie !== 'Não frequenta' ? answers.serie : null) || old.education || null,
      dados, anamnese: { respostas, atualizado_em: new Date().toISOString() },
    };
    const row = await NS.api(pid ? '/api/patients/' + pid : '/api/patients', {
      method: pid ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    await fillPick(row.id || pid);
    NS.setPatientFields({ name: row.name || name, birth_date: row.birth_date || body.birth_date, sex: row.sex || body.sex,
      education: row.education || body.education, application_date: $('#applicationDate')?.value });
    return { id: row.id || pid, respostas };
  }

  const busy = (b, on, txt) => { b.disabled = on; if (txt) b.textContent = txt; };
  $('#anamSave')?.addEventListener('click', async (e) => {
    const b = e.currentTarget; busy(b, true, 'Salvando…');
    try { await saveToPatient(); NS.toast('Anamnese salva no cadastro do paciente.'); NS.anamnesisAlert?.('Anamnese salva no cadastro do paciente (aba Pacientes).', 'done'); }
    catch (err) { NS.toast(err.message, true); }
    finally { busy(b, false, 'Salvar no paciente'); }
  });
  $('#anamGen')?.addEventListener('click', async (e) => {
    const b = e.currentTarget;
    if (!ITEMS.some(i => i.type !== 'txt' && i.type !== 'date' && answered(i.id))) { NS.toast('Marque as respostas da anamnese primeiro.', true); return; }
    busy(b, true, 'Gerando história… (até 1 min)');
    try {
      const { id, respostas } = await saveToPatient();
      const p = { name: $('#hvName').value.trim(), birth_date: $('#hvBirth').value, sex: answers.d_sexo || '' };
      const res = await NS.api('/api/ai/anamnesis-form', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patient: p, patient_id: id, respostas: { ...respostas, ...Object.fromEntries(Object.entries(answers).filter(([k]) => k.startsWith('d_'))) }, texto: toText() }) });
      NS.applyAnamnesis(res);
    } catch (err) { NS.toast(err.message, true); }
    finally { busy(b, false, 'Salvar e gerar história (1 crédito)'); }
  });
  $('#anamClear')?.addEventListener('click', () => { if (confirm('Limpar todas as marcações?')) { answers = {}; render(); } });

  // ---------- modos (upload × preencher) ----------
  function setMode(m) {
    document.querySelectorAll('[data-hv-mode]').forEach(b => b.classList.toggle('on', b.dataset.hvMode === m));
    $('#hvPanelUpload').hidden = m !== 'upload'; $('#hvPanelForm').hidden = m !== 'form';
    try { localStorage.setItem('ns.hvMode', m); } catch {}
  }
  document.querySelectorAll('[data-hv-mode]').forEach(b => b.addEventListener('click', () => setMode(b.dataset.hvMode)));
  let mode = 'upload'; try { mode = localStorage.getItem('ns.hvMode') || 'upload'; } catch {}
  setMode(mode === 'form' ? 'form' : 'upload');

  // ao abrir a aba História, atualiza a lista de pacientes
  window.addEventListener('hashchange', () => { if (location.hash.startsWith('#historia')) fillPick(); });
  if (location.hash.startsWith('#historia')) setTimeout(fillPick, 800);

  render();
  NS.anamForm = {
    // reabre respostas salvas (ex.: Testes realizados → Abrir)
    load(resp, pid) { answers = { ...(resp || {}) }; setMode('form'); render(); fillPick(pid || ''); },
    text: toText,
  };
  window.NS = NS;
})();
