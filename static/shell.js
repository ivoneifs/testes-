/* NeuroScore — shell de navegação, contas, administração e configurações.
   Depende de window.NS ({api, toast, esc, state}) exposto por app.js. */
(() => {
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => [...document.querySelectorAll(s)];

  // ---------------- Tema ----------------
  const THEME_KEY = 'ns-theme';
  function applyTheme(t) {
    const root = document.documentElement;
    if (t === 'light' || t === 'dark') root.setAttribute('data-theme', t);
    else root.removeAttribute('data-theme');
    try { localStorage.setItem(THEME_KEY, t); } catch {}
    $$('#themeSeg .seg-btn').forEach(b => b.classList.toggle('active', b.dataset.theme === (t || 'system')));
  }
  try { applyTheme(localStorage.getItem(THEME_KEY) || 'system'); } catch { applyTheme('system'); }

  // ---------------- Views / navegação ----------------
  const VIEWS = ['dashboard', 'pacientes', 'historia', 'laudos', 'realizados', 'geracao', 'videos', 'planos', 'config', 'admin', 'conta'];
  const TITLES = {
    dashboard: 'Dashboard', pacientes: 'Pacientes', historia: 'História de Vida',
    laudos: 'Laudos', realizados: 'Testes Realizados', videos: 'Vídeos dos Testes', geracao: 'Geração de Laudo Neuropsicológico', planos: 'Planos e Recargas', config: 'Configurações',
    admin: 'Administração', conta: 'Minha Conta',
  };
  let currentView = null;

  function showView(name) {
    name = String(name || '').split('?')[0];
    if (!VIEWS.includes(name)) name = 'dashboard';
    if (name === 'admin' && state.profile?.role !== 'admin') name = 'dashboard';
    // Teste expirado: só Planos (para comprar) e Conta; o resto fica atrás da tela de bloqueio.
    if (state.blocked) {
      const canBuy = state.blocked === 'trial_expired';
      const free = canBuy ? ['planos', 'conta'] : [];
      $('#blockedScreen').hidden = free.includes(name);
      if (!free.includes(name)) return;
    }
    currentView = name;
    VIEWS.forEach(v => { const el = $('#view-' + v); if (el) el.hidden = v !== name; });
    $$('#nav .nav-item').forEach(a => a.classList.toggle('active', a.dataset.view === name));
    $('#pageTitle').textContent = TITLES[name] || 'NeuroScore';
    $('#viewEyebrow').textContent = 'NeuroScore';
    $('#sidebar').classList.remove('open');
    if (location.hash.slice(1) !== name) history.replaceState(null, '', '#' + name);
    const load = VIEW_LOADERS[name];
    if (load) load();
    window.scrollTo(0, 0);
  }
  window.showView = showView;

  $('#nav').addEventListener('click', (e) => {
    const a = e.target.closest('.nav-item'); if (!a) return;
    if (a.id === 'logoutBtn') return;             // app.js trata o logout
    if (!a.dataset.view) return;
    e.preventDefault(); showView(a.dataset.view);
  });
  document.addEventListener('click', (e) => {
    const g = e.target.closest('[data-goto]'); if (g) { e.preventDefault(); showView(g.dataset.goto); }
  });
  window.addEventListener('hashchange', () => showView(location.hash.slice(1) || 'dashboard'));

  // ---------------- Config ----------------
  $('#themeSeg')?.addEventListener('click', (e) => {
    const b = e.target.closest('.seg-btn'); if (!b) return;
    applyTheme(b.dataset.theme);
    savePrefs();
  });
  ['prefEmail', 'prefTasks'].forEach(id => $('#' + id)?.addEventListener('change', savePrefs));
  async function savePrefs() {
    const prefs = {
      theme: (localStorage.getItem(THEME_KEY) || 'system'),
      notify_email: $('#prefEmail').checked,
      notify_tasks: $('#prefTasks').checked,
    };
    state.profile = { ...(state.profile || {}), prefs };
    try { await NS.api('/api/profile', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prefs }) }); }
    catch (e) { NS.toast(e.message, true); }
  }

  // ---------------- Conta ----------------
  function fillConta() {
    const p = state.profile || {};
    $('#acctName').value = p.full_name || '';
    $('#acctEmail').value = p.email || state.user?.email || '';
    $('#acctCrp').value = p.professional_id || '';
    $('#acctHeader').value = p.header || '';
  }
  $('#acctSaveBtn')?.addEventListener('click', async () => {
    const btn = $('#acctSaveBtn'); btn.disabled = true;
    const body = {
      full_name: $('#acctName').value.trim(),
      professional_id: $('#acctCrp').value.trim(),
      header: $('#acctHeader').value.trim(),
    };
    try {
      const row = await NS.api('/api/profile', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      state.profile = { ...(state.profile || {}), ...row };
      refreshIdentity();
      $('#acctMsg').textContent = 'Salvo.'; $('#acctMsg').className = 'inline-msg ok';
    } catch (e) { $('#acctMsg').textContent = e.message; $('#acctMsg').className = 'inline-msg err'; }
    finally { btn.disabled = false; setTimeout(() => { $('#acctMsg').textContent = ''; }, 3000); }
  });
  $('#pwBtn')?.addEventListener('click', async () => {
    const a = $('#pwNew').value, b = $('#pwNew2').value;
    const msg = $('#pwMsg');
    if (a.length < 6) { msg.textContent = 'Mínimo 6 caracteres.'; msg.className = 'inline-msg err'; return; }
    if (a !== b) { msg.textContent = 'As senhas não conferem.'; msg.className = 'inline-msg err'; return; }
    $('#pwBtn').disabled = true;
    try {
      const { error } = await state.sb.auth.updateUser({ password: a });
      if (error) throw error;
      $('#pwNew').value = $('#pwNew2').value = '';
      msg.textContent = 'Senha alterada.'; msg.className = 'inline-msg ok';
    } catch (e) { msg.textContent = e.message || 'Falha ao alterar senha.'; msg.className = 'inline-msg err'; }
    finally { $('#pwBtn').disabled = false; }
  });

  const fmtCred = (n) => Number(n || 0).toLocaleString('pt-BR', { maximumFractionDigits: 2 });
  NS.fmtCred = fmtCred;
  function refreshIdentity() {
    const p = state.profile || {};
    const roleEl = $('#userRole');
    if (roleEl) { roleEl.textContent = p.role === 'admin' ? 'Administrador' : (p.trial_ends_at ? 'Teste' : 'Pro'); roleEl.hidden = false; }
    $('#userEmail').textContent = p.full_name || p.email || state.user?.email || '';
    const first = String(p.full_name || '').trim().split(/\s+/)[0];
    $('#welcomeTitle').textContent = first ? `Olá, ${first}! Bem-vindo ao NeuroScore` : 'Bem-vindo ao NeuroScore';
    $('#navAdmin').hidden = p.role !== 'admin';
    const cc = $('#creditCard');
    if (cc) {
      $('#creditBalance').textContent = fmtCred(p.credits);
      cc.hidden = p.role === 'admin';           // admin não usa créditos
      cc.classList.toggle('credit-card--empty', p.role !== 'admin' && Number(p.credits || 0) < 0.5);
    }
    // saldo zerado: avisa que os serviços pagos estão bloqueados
    const out = p.role !== 'admin' && state.authEnabled && Number(p.credits || 0) < 0.5 && !state.blocked;
    $('#creditsBanner').hidden = !out;
  }

  // ---------------- Dashboard ----------------
  function miniBars(items, label, val, unit) {
    if (!items.length) return '<p class="muted small">Sem dados ainda.</p>';
    const max = Math.max(...items.map(val), 1);
    return `<div class="minichart">${items.map(it => `
      <div class="minibar-row" title="${NS.esc(String(val(it)))} ${unit}">
        <span class="minibar-lbl">${NS.esc(String(label(it)))}</span>
        <span class="minibar-track"><span class="minibar-fill" style="width:${(val(it) / max * 100).toFixed(1)}%"></span></span>
        <span class="minibar-val">${val(it)}</span>
      </div>`).join('')}</div>`;
  }
  async function loadDashboard() {
    try {
      const [sum, { evaluations = [] }] = await Promise.all([
        NS.api('/api/dashboard').catch(() => ({})),
        NS.api('/api/evaluations').catch(() => ({ evaluations: [] })),
      ]);
      $('#kpiEvals').textContent = sum.evaluations ?? evaluations.length;
      $('#kpiPatients').textContent = sum.patients ?? (state.patients || []).length;
      $('#kpiCredits').textContent = state.profile?.role === 'admin' ? '∞' : fmtCred(state.profile?.credits);
      $('#kpiTests').textContent = state.tests?.length ?? 62;
      const MES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
      const fmtM = (m) => { const [y, mo] = m.split('-'); return `${MES[+mo - 1]}/${y.slice(2)}`; };
      $('#dashByMonth').innerHTML = miniBars(sum.by_month || [], d => fmtM(d.m), d => d.n, 'avaliações');
      $('#dashTopTests').innerHTML = miniBars(sum.top_tests || [], d => d.t, d => d.n, 'usos');
      $('#dashRecent').innerHTML = evaluations.slice(0, 8).map(ev => {
        const nm = NS.esc(ev.patient?.name || '(sem nome)');
        const when = new Date(ev.updated_at || ev.created_at).toLocaleString('pt-BR');
        const tests = (ev.tests || []).map(t => t.test).filter(Boolean).join(', ');
        return `<div class="list-row" data-open-eval="${ev.id}"><div><b>${nm}</b><small>${NS.esc(tests || 'sem testes')}</small></div><span class="muted small">${when}</span></div>`;
      }).join('') || '<p class="muted small">Nenhuma avaliação ainda.</p>';
    } catch (e) { NS.toast(e.message, true); }
  }
  document.addEventListener('click', async (e) => {
    const r = e.target.closest('[data-open-eval]'); if (!r) return;
    try {
      const ev = await NS.api('/api/evaluations/' + r.dataset.openEval);
      window.loadEvaluation && window.loadEvaluation(ev);
      showView('laudos'); NS.toast('Avaliação carregada.');
    } catch (err) { NS.toast(err.message, true); }
  });

  // ---------------- Pacientes ----------------
  async function loadPatients() {
    const body = $('#patientsBody');
    try {
      const [{ patients = [] }, { evaluations = [] }] = await Promise.all([
        NS.api('/api/patients'),
        NS.api('/api/evaluations').catch(() => ({ evaluations: [] })),
      ]);
      state.patients = patients;
      state.allEvals = evaluations;
      const cnt = {};
      evaluations.forEach(e => { if (e.patient_id) cnt[e.patient_id] = (cnt[e.patient_id] || 0) + 1; });
      $('#patientOptions').innerHTML = patients.map(p => `<option value="${NS.esc(p.name)}">`).join('');
      body.innerHTML = patients.map(p => `<tr>
        <td>${NS.esc(p.name)}</td><td>${NS.esc(p.birth_date || '—')}</td>
        <td>${NS.esc(p.sex || '—')}</td><td>${NS.esc(p.education || '—')}</td>
        <td>${cnt[p.id] ? `<button class="btn ghost xs" data-evals-pat="${p.id}">${cnt[p.id]} laudo(s)</button>` : '<span class="muted">—</span>'}</td>
        <td class="row-acts">
          <button class="btn ghost xs" data-anam-pat="${p.id}" title="Anamnese (História de Vida)">${(p.anamnese || {}).atualizado_em ? '📇 Anamnese ✓' : '📇 Anamnese'}</button>
          <button class="btn ghost xs" data-use="${p.id}">Usar</button>
          <button class="btn ghost xs" data-edit-pat="${p.id}">Editar</button>
          <button class="btn ghost xs danger" data-del-pat="${p.id}">Excluir</button>
        </td></tr>`).join('') || '<tr><td colspan="6" class="muted small">Nenhum paciente cadastrado.</td></tr>';
    } catch (e) { body.innerHTML = `<tr><td colspan="6" class="inline-msg err">${NS.esc(e.message)}</td></tr>`; }
  }
  $('#patientsBody')?.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-evals-pat]'); if (!b) return;
    const p = state.patients.find(x => x.id === b.dataset.evalsPat);
    try {
      const { evaluations = [] } = await NS.api('/api/evaluations?patient=' + b.dataset.evalsPat);
      openEdit(`Avaliações — ${p ? p.name : ''}`,
        `<div class="list-plain" style="grid-column:1/-1">${evaluations.map(ev => {
          const when = new Date(ev.updated_at || ev.created_at).toLocaleDateString('pt-BR');
          const tests = (ev.tests || []).map(t => t.test).filter(Boolean).join(', ') || 'sem testes';
          return `<div class="list-row" data-open-eval="${ev.id}" style="cursor:pointer"><div><b>${when}</b><small>${NS.esc(tests)}</small></div><span class="muted small">abrir ›</span></div>`;
        }).join('') || '<p class="muted small">Nenhuma.</p>'}</div>`, null);
      $('#editSave').style.display = 'none';
    } catch (err) { NS.toast(err.message, true); }
  });
  $('#patientNewBtn')?.addEventListener('click', () => patientForm());
  $('#patientsBody')?.addEventListener('click', async (e) => {
    const t = e.target;
    if (t.dataset.editPat) return patientForm(state.patients.find(p => p.id === t.dataset.editPat));
    if (t.dataset.anamPat) {
      const p = state.patients.find(x => x.id === t.dataset.anamPat); if (!p) return;
      showView('historia');
      NS.anamForm?.load({ ...((p.anamnese || {}).respostas || {}), ...Object.fromEntries(Object.entries(p.dados || {}).map(([k, v]) => ['d_' + k, v])), d_sexo: (p.dados || {}).sexo || p.sex || '' }, p.id);
      NS.setPatientFields({ name: p.name, birth_date: p.birth_date, sex: p.sex, education: p.education, application_date: $('#applicationDate')?.value });
      return;
    }
    if (t.dataset.use) {
      const p = state.patients.find(x => x.id === t.dataset.use); if (!p) return;
      $('#patientName').value = p.name || ''; $('#birthDate').value = p.birth_date || '';
      $('#sex').value = p.sex || ''; $('#education').value = p.education || '';
      document.dispatchEvent(new Event('ns-patient-loaded'));
      showView('laudos'); NS.toast('Paciente carregado na avaliação.');
    }
    if (t.dataset.delPat) {
      if (!confirm('Excluir este paciente?')) return;
      try { await NS.api('/api/patients/' + t.dataset.delPat, { method: 'DELETE' }); loadPatients(); NS.toast('Paciente excluído.'); }
      catch (err) { NS.toast(err.message, true); }
    }
  });
  // identificação da ficha de anamnese (patients.dados) — a mesma da aba História de Vida
  const PAT_DADOS = [['responsavel', 'Responsável', 1], ['mae', 'Nome da mãe', 1], ['pai', 'Nome do pai', 1],
    ['cpf', 'CPF'], ['telefone', 'Fone'], ['naturalidade', 'Naturalidade'], ['lateralidade', 'Lateralidade'],
    ['endereco', 'Endereço', 1], ['cidade', 'Cidade'], ['solicitante', 'Solicitante'], ['especialidade', 'Especialidade'],
    ['hipotese', 'Hipótese diagnóstica', 1]];
  function patientForm(p) {
    p = p || {};
    openEdit(p.id ? 'Editar paciente' : 'Novo paciente', `
      <label class="field span-2">Nome<input id="f_name" value="${NS.esc(p.name || '')}"></label>
      <label class="field">Nascimento<input id="f_birth" type="date" value="${NS.esc(p.birth_date || '')}"></label>
      <label class="field">Sexo<select id="f_sex"><option value="">—</option>
        <option${p.sex === 'Feminino' ? ' selected' : ''}>Feminino</option>
        <option${p.sex === 'Masculino' ? ' selected' : ''}>Masculino</option></select></label>
      <label class="field span-2">Escolaridade<input id="f_edu" value="${NS.esc(p.education || '')}"></label>
      ${PAT_DADOS.map(([k, l, span]) => `<label class="field${span ? ' span-2' : ''}">${l}<input data-dado="${k}" value="${NS.esc((p.dados || {})[k] || '')}"></label>`).join('')}
      <label class="field span-2">Notas<textarea id="f_notes" rows="2">${NS.esc(p.notes || '')}</textarea></label>`,
      async () => {
        const dados = { ...(p.dados || {}) };
        document.querySelectorAll('#editBody [data-dado]').forEach(i => { dados[i.dataset.dado] = i.value.trim(); });
        const body = {
          name: $('#f_name').value.trim(), birth_date: $('#f_birth').value || null,
          sex: $('#f_sex').value || null, education: $('#f_edu').value.trim() || null,
          notes: $('#f_notes').value.trim() || null, dados,
        };
        if (!body.name) throw new Error('Informe o nome.');
        const url = p.id ? '/api/patients/' + p.id : '/api/patients';
        await NS.api(url, { method: p.id ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        loadPatients();
      });
  }

  // ---------------- Planos ----------------
  const brl = (cents) => (Number(cents || 0) / 100).toLocaleString('pt-BR', { minimumFractionDigits: 2 });
  async function loadPlanos() {
    try {
      const { plans = [] } = await NS.api('/api/plans');
      state.plans = plans;
      const active = plans.filter(p => p.active);
      $('#planosGrid').innerHTML = active.map(p => `
        <div class="plano${p.featured ? ' plano--feat' : ''}">
          ${p.featured ? '<span class="plano-tag">Mais vendido</span>' : ''}
          <h3>${NS.esc(p.name)}</h3>
          <div class="plano-price">R$ ${brl(p.amount_cents)}<span>/ pacote</span></div>
          <div class="plano-laudos">${p.credits} créditos · R$ ${brl(Math.round(p.amount_cents / (p.credits || 1)))} cada</div>
          <ul>${(p.features || []).map(i => `<li>${NS.esc(i)}</li>`).join('')}</ul>
          <button class="btn primary" data-buy="${NS.esc(p.key)}">Comprar agora</button>
        </div>`).join('') || '<p class="muted">Nenhum pacote disponível.</p>';
    } catch (e) { $('#planosGrid').innerHTML = `<p class="inline-msg err">${NS.esc(e.message)}</p>`; }
  }
  $('#planosGrid')?.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-buy]'); if (!b) return;
    b.disabled = true; const t = b.textContent; b.textContent = 'Redirecionando…';
    try {
      const { init_point } = await NS.api('/api/checkout', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pack: b.dataset.buy }),
      });
      if (init_point) location.href = init_point;
      else throw new Error('Checkout indisponível.');
    } catch (err) { NS.toast(err.message, true); b.disabled = false; b.textContent = t; }
  });

  async function refreshCredits() {
    try {
      const p = await NS.api('/api/profile');
      state.profile = { ...(state.profile || {}), ...p };
      refreshIdentity();
      if (!$('#view-dashboard').hidden) loadDashboard();
    } catch {}
  }
  window.afterLaudo = refreshCredits;
  window.NS && (window.NS.goPlanos = () => showView('planos'));

  // ---------------- Administração ----------------
  async function loadAdmin() {
    try {
      const { professionals = [] } = await NS.api('/api/admin/professionals');
      state.pros = professionals;
      renderPros();
    } catch (e) { $('#prosBody').innerHTML = `<tr><td colspan="8" class="inline-msg err">${NS.esc(e.message)}</td></tr>`; }
    try {
      const { plans = [] } = await NS.api('/api/plans');
      state.plans = plans;
      $('#plansBody').innerHTML = plans.map(p => `<tr>
        <td>${NS.esc(p.name)} <span class="muted small">(${NS.esc(p.key)})</span></td>
        <td>${p.credits}</td><td>${brl(p.amount_cents)}</td>
        <td>${p.featured ? '★' : '—'}</td>
        <td><span class="pill${p.active ? ' pill--ok' : ' pill--off'}">${p.active ? 'Sim' : 'Não'}</span></td>
        <td class="row-acts"><button class="btn ghost xs" data-edit-plan="${NS.esc(p.key)}">Editar</button>
          <button class="btn ghost xs danger" data-del-plan="${NS.esc(p.key)}">Excluir</button></td>
      </tr>`).join('') || '<tr><td colspan="6" class="muted small">Nenhum pacote.</td></tr>';
    } catch (e) { $('#plansBody').innerHTML = `<tr><td colspan="6" class="inline-msg err">${NS.esc(e.message)}</td></tr>`; }
    try {
      const { site = {} } = await NS.api('/api/site');
      state.site = site; fillSiteForm(site);
    } catch {}
  }

  // ---------------- Aparência do site ----------------
  const SITE_DEFAULT_COLORS = { primary: '#4f46e5', accent: '#f97316', secondary: '#06b6d4', dark: '#0f172a' };
  function fillSiteForm(site) {
    const c = { ...SITE_DEFAULT_COLORS, ...(site.colors || {}) };
    $('#siteColorPrimary').value = c.primary; $('#siteColorAccent').value = c.accent;
    $('#siteColorSecondary').value = c.secondary; $('#siteColorDark').value = c.dark;
    $('#siteHeroTitle').value = site.hero_title || ''; $('#siteHeroSub').value = site.hero_subtitle || '';
    $('#siteCta').value = site.cta_text || ''; $('#siteWhats').value = site.whatsapp || '';
    $('#siteEmail').value = site.email || '';
  }
  async function saveSite(colors) {
    const msg = $('#siteMsg');
    const data = {
      colors: colors || {
        primary: $('#siteColorPrimary').value, accent: $('#siteColorAccent').value,
        secondary: $('#siteColorSecondary').value, dark: $('#siteColorDark').value,
      },
      hero_title: $('#siteHeroTitle').value.trim(), hero_subtitle: $('#siteHeroSub').value.trim(),
      cta_text: $('#siteCta').value.trim(), whatsapp: $('#siteWhats').value.replace(/\D/g, ''),
      email: $('#siteEmail').value.trim(),
    };
    try {
      const { site } = await NS.api('/api/admin/site', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
      });
      state.site = site; fillSiteForm(site); applySiteColors(site);
      msg.textContent = 'Aparência salva.'; msg.className = 'inline-msg ok';
    } catch (e) { msg.textContent = e.message; msg.className = 'inline-msg err'; }
  }
  $('#siteSaveBtn')?.addEventListener('click', () => saveSite());
  $('#siteResetBtn')?.addEventListener('click', () => {
    if (confirm('Voltar às cores padrão do site?')) saveSite({ ...SITE_DEFAULT_COLORS });
  });
  $('#planNewBtn')?.addEventListener('click', () => {
    openEdit('Novo pacote', `
      <label class="field">Código (sem espaços)<input id="f_key" placeholder="pack40"></label>
      <label class="field">Nome<input id="f_name" placeholder="Pack 40 créditos"></label>
      <label class="field">Créditos (laudos)<input id="f_credits" type="number" step="0.5" value="10"></label>
      <label class="field">Preço R$<input id="f_price" type="number" step="0.01" value="200.00"></label>
      <label class="field">Ordem<input id="f_sort" type="number" value="${(state.plans || []).length + 1}"></label>
      <label class="field span-2">Itens (um por linha)<textarea id="f_feat" rows="4"></textarea></label>
      <label class="switch-row"><div><b>Destaque</b><small>"Mais vendido"</small></div><input type="checkbox" class="switch" id="f_featured"></label>`,
      async () => {
        const key = $('#f_key').value.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '');
        if (!key) throw new Error('Informe o código do pacote.');
        if ((state.plans || []).some(p => p.key === key)) throw new Error('Já existe um pacote com esse código.');
        await NS.api('/api/admin/plans/' + key, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: $('#f_name').value.trim() || key,
            credits: parseFloat($('#f_credits').value) || 0,
            amount_cents: Math.round(parseFloat($('#f_price').value) * 100) || 0,
            sort: Number($('#f_sort').value) || 0,
            features: $('#f_feat').value.split('\n').map(s => s.trim()).filter(Boolean),
            featured: $('#f_featured').checked, active: true,
          }),
        });
        loadAdmin();
      });
  });
  $('#proNewBtn')?.addEventListener('click', () => {
    openEdit('Novo profissional', `
      <label class="field span-2">E-mail<input id="f_email" type="email"></label>
      <label class="field">Senha inicial<input id="f_pw" type="text" placeholder="mín. 6 caracteres"></label>
      <label class="field">Nome<input id="f_fn"></label>
      <label class="field">CRP<input id="f_crp"></label>
      ${ACCESS_FIELDS('trial', 14)}
      <label class="field">Créditos iniciais<input id="f_credits" type="number" step="0.5" value="3"></label>`,
      async () => {
        await NS.api('/api/admin/professionals', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: $('#f_email').value.trim(), password: $('#f_pw').value,
            full_name: $('#f_fn').value.trim(), professional_id: $('#f_crp').value.trim(),
            credits: parseFloat($('#f_credits').value) || 0, ...accessPayload(),
          }),
        });
        loadAdmin();
      });
  });
  $('#plansBody')?.addEventListener('click', async (e) => {
    const d = e.target.closest('[data-del-plan]');
    if (d) {
      if (!confirm('Excluir este pacote? Ele some da landing page e da tela de Planos.')) return;
      try { await NS.api('/api/admin/plans/' + d.dataset.delPlan, { method: 'DELETE' }); loadAdmin(); NS.toast('Pacote excluído.'); }
      catch (err) { NS.toast(err.message, true); }
      return;
    }
    const b = e.target.closest('[data-edit-plan]'); if (!b) return;
    const p = (state.plans || []).find(x => x.key === b.dataset.editPlan); if (!p) return;
    openEdit('Editar ' + p.name, `
      <label class="field span-2">Nome<input id="f_name" value="${NS.esc(p.name)}"></label>
      <label class="field">Créditos (laudos)<input id="f_credits" type="number" step="0.5" value="${p.credits}"></label>
      <label class="field">Preço R$<input id="f_price" type="number" step="0.01" value="${(p.amount_cents / 100).toFixed(2)}"></label>
      <label class="field">Ordem<input id="f_sort" type="number" value="${p.sort ?? 0}"></label>
      <label class="field span-2">Itens (um por linha)<textarea id="f_feat" rows="4">${NS.esc((p.features || []).join('\n'))}</textarea></label>
      <label class="switch-row"><div><b>Destaque</b><small>"Mais vendido"</small></div><input type="checkbox" class="switch" id="f_featured" ${p.featured ? 'checked' : ''}></label>
      <label class="switch-row"><div><b>Ativo</b><small>Aparece na tela de Planos</small></div><input type="checkbox" class="switch" id="f_active" ${p.active ? 'checked' : ''}></label>`,
      async () => {
        await NS.api('/api/admin/plans/' + p.key, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: $('#f_name').value.trim(),
            credits: parseFloat($('#f_credits').value) || 0,
            amount_cents: Math.round(parseFloat($('#f_price').value) * 100) || 0,
            features: $('#f_feat').value.split('\n').map(s => s.trim()).filter(Boolean),
            featured: $('#f_featured').checked, active: $('#f_active').checked,
            sort: Number($('#f_sort').value) || 0,
          }),
        });
        loadAdmin();
      });
  });
  function accessOf(p) {
    if (p.role === 'admin') return { key: 'admin', label: 'Admin', cls: ' pill--admin' };
    if (!p.trial_ends_at) return { key: 'pro', label: 'Pro', cls: ' pill--ok' };
    const left = Math.ceil((new Date(p.trial_ends_at) - Date.now()) / 86400000);
    return left > 0
      ? { key: 'trial', left, label: `Teste · ${left} dia${left === 1 ? '' : 's'}`, cls: ' pill--trial' }
      : { key: 'trial', left: 0, label: 'Teste expirado', cls: ' pill--off' };
  }
  const ACCESS_FIELDS = (cur = 'trial', days = 14) => `
      <label class="field">Tipo de acesso<select id="f_access">
        <option value="pro"${cur === 'pro' ? ' selected' : ''}>Pro (acesso completo)</option>
        <option value="trial"${cur === 'trial' ? ' selected' : ''}>Teste (trial)</option>
        <option value="admin"${cur === 'admin' ? ' selected' : ''}>Administrador</option></select></label>
      <label class="field" id="f_days_row"${cur === 'trial' ? '' : ' hidden'}>Dias de teste (a partir de hoje)<input id="f_days" type="number" min="0" value="${days}"></label>`;
  document.addEventListener('change', (e) => {
    if (e.target.id === 'f_access') $('#f_days_row').hidden = e.target.value !== 'trial';
  });
  const accessPayload = () => {
    const access = $('#f_access').value;
    return access === 'trial'
      ? { access, trial_days: Math.max(0, parseInt($('#f_days').value, 10) || 0) }
      : { access };
  };
  function renderPros() {
    const q = ($('#proSearch').value || '').toLowerCase();
    const rows = (state.pros || []).filter(p =>
      !q || (p.full_name || '').toLowerCase().includes(q) || (p.email || '').toLowerCase().includes(q));
    $('#prosBody').innerHTML = rows.map(p => `<tr>
      <td>${NS.esc(p.full_name || '—')}</td><td>${NS.esc(p.email || '—')}</td>
      <td>${NS.esc(p.professional_id || '—')}</td>
      <td><span class="pill${accessOf(p).cls}">${accessOf(p).label}</span></td>
      <td><span class="pill${p.status === 'suspended' ? ' pill--off' : ' pill--ok'}">${p.status === 'suspended' ? 'Suspenso' : 'Ativo'}</span></td>
      <td>${NS.esc(p.plan || '—')}</td><td>${p.role === 'admin' ? '∞' : fmtCred(p.credits)}</td>
      <td class="row-acts">
        <button class="btn ghost xs" data-grant-pro="${p.id}">+ créditos</button>
        <button class="btn ghost xs" data-edit-pro="${p.id}">Editar</button>
        <button class="btn ghost xs" data-pw-pro="${p.id}">Senha</button>
        <button class="btn ghost xs danger" data-del-pro="${p.id}">Excluir</button>
      </td></tr>`).join('') || '<tr><td colspan="8" class="muted small">Nenhum profissional.</td></tr>';
  }
  $('#proSearch')?.addEventListener('input', renderPros);
  $('#prosBody')?.addEventListener('click', async (e) => {
    const t = e.target;
    if (t.dataset.grantPro) {
      const p = state.pros.find(x => x.id === t.dataset.grantPro); if (!p) return;
      const v = prompt(`Créditos para ${p.full_name || p.email} (use número negativo para debitar):`, '20');
      if (v === null) return;
      const n = parseFloat(String(v).replace(',', '.'));
      if (!Number.isFinite(n) || n === 0) { NS.toast('Valor inválido.', true); return; }
      try {
        const { balance } = await NS.api('/api/admin/professionals/' + p.id + '/credits', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ delta: n }),
        });
        NS.toast(`Saldo de ${p.full_name || p.email}: ${fmtCred(balance)} créditos.`);
        loadAdmin();
        if (p.id === state.profile?.id) refreshCredits();
      } catch (err) { NS.toast(err.message, true); }
      return;
    }
    if (t.dataset.pwPro) {
      const p = state.pros.find(x => x.id === t.dataset.pwPro); if (!p) return;
      openEdit('Nova senha — ' + (p.full_name || p.email), `
        <label class="field">Nova senha<input id="f_pw1" type="text" minlength="6" autocomplete="off"></label>
        <label class="field">Confirmar<input id="f_pw2" type="text" minlength="6" autocomplete="off"></label>
        <span class="muted small span-2">A senha antiga deixa de funcionar na hora. Envie a nova ao usuário.</span>`,
        async () => {
          const pw = $('#f_pw1').value;
          if (pw.length < 6) throw new Error('Mínimo de 6 caracteres.');
          if (pw !== $('#f_pw2').value) throw new Error('As senhas não conferem.');
          await NS.api('/api/admin/professionals/' + p.id + '/password', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: pw }),
          });
        });
      return;
    }
    if (t.dataset.editPro) {
      const p = state.pros.find(x => x.id === t.dataset.editPro); if (!p) return;
      openEdit('Editar profissional', `
        <label class="field span-2">Nome<input id="f_fn" value="${NS.esc(p.full_name || '')}"></label>
        <label class="field">CRP<input id="f_crp" value="${NS.esc(p.professional_id || '')}"></label>
        ${ACCESS_FIELDS(accessOf(p).key, accessOf(p).key === 'trial' ? accessOf(p).left : 14)}
        <label class="field">Status<select id="f_status">
          <option value="active"${p.status !== 'suspended' ? ' selected' : ''}>Ativo</option>
          <option value="suspended"${p.status === 'suspended' ? ' selected' : ''}>Suspenso</option></select></label>
        <label class="field">Plano<input id="f_plan" value="${NS.esc(p.plan || '')}"></label>
        <label class="field">Créditos<input id="f_credits" type="number" step="0.5" value="${p.credits ?? 0}"></label>`,
        async () => {
          await NS.api('/api/admin/professionals/' + p.id, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              full_name: $('#f_fn').value.trim(), professional_id: $('#f_crp').value.trim(),
              status: $('#f_status').value, ...accessPayload(),
              plan: $('#f_plan').value.trim() || null, credits: parseFloat($('#f_credits').value) || 0,
            }),
          });
          loadAdmin();
        });
    }
    if (t.dataset.delPro) {
      if (!confirm('Excluir este profissional? Esta ação remove o acesso e os dados dele.')) return;
      try { await NS.api('/api/admin/professionals/' + t.dataset.delPro, { method: 'DELETE' }); loadAdmin(); NS.toast('Profissional excluído.'); }
      catch (err) { NS.toast(err.message, true); }
    }
  });

  // ---------------- Testes realizados (CRUD) ----------------
  const fmtDT = (d) => new Date(d).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
  const HV = 'História de Vida';
  function trSummary(r) {
    if (r.test === HV) {
      const t = String(((r.result || {}).historia_modelo || {}).historia_doenca_atual || (r.result || {}).resumo || '').trim();
      const files = ((r.inputs || {}).arquivos || []).length;
      const form = (r.inputs || {}).formulario;
      return `<span>${NS.esc(t.length > 220 ? t.slice(0, 220) + '…' : t)}</span>${files ? `<span>Anamnese: <b>${files} arquivo(s) (OCR)</b></span>` : ''}${form ? '<span>Anamnese: <b>preenchida online</b></span>' : ''}`;
    }
    // primeira tabela do resultado: até 4 linhas "rótulo: valor"
    const t = ((r.result || {}).tables || [])[0]; if (!t) return '';
    return (t.rows || []).slice(0, 4).map(row => {
      const v = row.values || []; return v.length > 1 ? `<span>${NS.esc(String(v[0] ?? ''))}: <b>${NS.esc(String(v[1] ?? ''))}</b></span>` : '';
    }).join('');
  }
  async function loadRealizados() {
    try {
      const { results = [] } = await NS.api('/api/test-results');
      state.tr = results;
      const groups = new Map();
      for (const r of results) {
        if (!groups.has(r.patient_key)) groups.set(r.patient_key, { p: r.patient || {}, n: 0, last: r.updated_at });
        groups.get(r.patient_key).n++;
      }
      state.trGroups = groups;
      const sel = $('#trPatient'), cur = state.trKey && groups.has(state.trKey) ? state.trKey : [...groups.keys()][0];
      sel.innerHTML = [...groups.entries()].map(([k, g]) =>
        `<option value="${NS.esc(k)}"${k === cur ? ' selected' : ''}>${NS.esc(g.p.name || '(sem nome)')}${g.p.birth_date ? ' · nasc. ' + g.p.birth_date.split('-').reverse().join('/') : ''} — ${g.n} teste(s)</option>`).join('')
        || '<option value="">Nenhum teste salvo ainda</option>';
      state.trKey = cur || null;
      state.trSel = state.trSel || {};
      renderRealizados();
    } catch (e) { $('#trList').innerHTML = `<p class="inline-msg err">${NS.esc(e.message)}</p>`; }
  }
  function renderRealizados() {
    const recs = (state.tr || []).filter(r => r.patient_key === state.trKey);
    $('#trList').innerHTML = recs.map(r => {
      const on = state.trSel[r.id] !== false;
      return `<article class="tr-card${on ? ' on' : ''}${r.test === HV ? ' hv' : ''}">
        <label class="tr-check" title="Incluir no laudo completo"><input type="checkbox" data-tr-sel="${r.id}"${on ? ' checked' : ''}><span></span></label>
        <div class="tr-body">
          <h3>${NS.esc(NS.testLabel ? NS.testLabel(r.test) : r.test)}</h3>
          <div class="muted small">Atualizado em ${fmtDT(r.updated_at)}${r.patient?.application_date ? ' · aplicação ' + r.patient.application_date.split('-').reverse().join('/') : ''}</div>
          <div class="tr-sum">${trSummary(r)}</div>
        </div>
        <div class="row-acts">
          ${r.test !== HV ? `<button class="btn ghost xs" data-tr-solo="${r.id}" title="Laudo neuropsicológico só deste teste (+ História de Vida)">Laudo deste teste</button>` : ''}
          ${(r.result || {}).externo ? '<span class="muted small" title="Relatório já corrigido (transcrito do arquivo enviado)">relatório enviado</span>' : `<button class="btn ghost xs" data-tr-open="${r.id}">Abrir / editar</button>`}
          <button class="btn ghost xs danger" data-tr-del="${r.id}">Excluir</button>
        </div></article>`;
    }).join('') || `<div class="empty-state">Nenhum teste salvo para este paciente. Corrija um teste em <a href="#laudos">Laudos</a> ou leia a anamnese em <a href="#historia">História de Vida</a>: ele aparece aqui.</div>`;
    const n = recs.filter(r => state.trSel[r.id] !== false).length;
    $('#trFinal').hidden = !recs.length;
    $('#trFinalInfo').textContent = `${n} de ${recs.length} teste(s) selecionado(s). Gera o Laudo Neuropsicológico completo no seu modelo, com a História de Vida e os testes marcados (1 crédito).`;
    $('#trLaudoBtn').disabled = !n;
  }
  $('#trPatient')?.addEventListener('change', (e) => { state.trKey = e.target.value; renderRealizados(); });
  $('#trList')?.addEventListener('change', (e) => {
    const c = e.target.closest('[data-tr-sel]'); if (!c) return;
    state.trSel[c.dataset.trSel] = c.checked; renderRealizados();
  });
  $('#trList')?.addEventListener('click', async (e) => {
    const o = e.target.closest('[data-tr-open]'), d = e.target.closest('[data-tr-del]'), so = e.target.closest('[data-tr-solo]');
    if (so) {
      const rec = state.tr.find(x => x.id === so.dataset.trSolo); if (!rec) return;
      const hv = state.tr.find(x => x.patient_key === rec.patient_key && x.test === HV);
      showView('geracao'); NS.glFromSaved([rec, ...(hv ? [hv] : [])], 'teste_isolado'); return;
    }
    if (o) {
      const rec = state.tr.find(x => x.id === o.dataset.trOpen); if (!rec) return;
      if (rec.test === HV) { showView('historia'); NS.openSavedHistoria(rec); return; }
      showView('laudos');
      try { await NS.openSavedTest(rec); NS.toast(`${rec.test} aberto. Altere e clique em Calcular para atualizar.`); }
      catch (err) { NS.toast(err.message, true); }
    }
    if (d) {
      if (!confirm('Excluir este teste salvo?')) return;
      try { await NS.api('/api/test-results/' + d.dataset.trDel, { method: 'DELETE' }); NS.toast('Teste excluído.'); loadRealizados(); }
      catch (err) { NS.toast(err.message, true); }
    }
  });
  $('#trLaudoBtn')?.addEventListener('click', () => {
    const recs = (state.tr || []).filter(r => r.patient_key === state.trKey && state.trSel[r.id] !== false);
    if (!recs.length) return;
    showView('geracao');
    NS.glFromSaved(recs, 'completo');
  });

  // ---------------- Vídeos explicativos ----------------
  function ytId(url) {
    const m = String(url || '').match(/(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([\w-]{11})/);
    return m ? m[1] : null;
  }
  async function loadVideos() {
    const isAdmin = state.profile?.role === 'admin';
    $('#videoNewBtn').hidden = !isAdmin;
    try {
      const { videos = [], platform_url } = await NS.api('/api/videos');
      state.videos = videos;
      if (platform_url) $('#videoPlatform').href = platform_url;
      renderVideos();
    } catch (e) { $('#videoGrid').innerHTML = `<p class="inline-msg err">${NS.esc(e.message)}</p>`; }
  }
  function renderVideos() {
    const isAdmin = state.profile?.role === 'admin';
    const q = ($('#videoSearch').value || '').toLowerCase();
    const vf = state.videoFilter || '';
    const list = (state.videos || []).filter(v => (!vf || v.test === vf)
      && (!q || `${v.title} ${v.test || ''} ${v.description || ''}`.toLowerCase().includes(q)));
    $('#videoGrid').innerHTML = list.map(v => {
      const yt = ytId(v.url);
      const thumb = yt ? `<img src="https://i.ytimg.com/vi/${yt}/mqdefault.jpg" alt="" loading="lazy">`
        : `<span class="video-ph"><b>${NS.esc(v.title)}</b><small>${/drive\.google\.com/.test(v.url) ? '🎬 Aulas no Google Drive' : '▶ Assistir'}</small></span>`;
      return `<article class="video-card">
        <a class="video-thumb" href="${NS.esc(v.url)}" target="_blank" rel="noopener">${thumb}<i>▶</i></a>
        <div class="video-body">
          ${v.test ? `<span class="pill">${NS.esc(v.test)}</span>` : ''}
          <h3>${NS.esc(v.title)}</h3>
          ${v.description ? `<p>${NS.esc(v.description)}</p>` : ''}
          <div class="row-acts">
            <a class="btn primary xs" href="${NS.esc(v.url)}" target="_blank" rel="noopener">Assistir ↗</a>
            ${isAdmin ? `<button class="btn ghost xs" data-edit-video="${v.id}">Editar</button>
              <button class="btn ghost xs danger" data-del-video="${v.id}">Excluir</button>` : ''}
          </div>
        </div></article>`;
    }).join('') || `<div class="empty-state">${(state.videos || []).length ? 'Nenhum vídeo encontrado.'
      : (isAdmin ? 'Nenhum vídeo cadastrado. Clique em "+ Novo vídeo" e cole o link da aula.' : 'Os vídeos explicativos aparecerão aqui em breve.')}</div>`;
  }
  function videoForm(v = {}) {
    const tests = (state.tests || []).map(t => `<option value="${NS.esc(t.name || t)}">`).join('');
    return `
      <label class="field span-2">Título<input id="f_vtitle" value="${NS.esc(v.title || '')}" placeholder="Ex.: WISC-IV: aplicação e correção"></label>
      <label class="field span-2">Link do vídeo<input id="f_vurl" type="url" value="${NS.esc(v.url || '')}" placeholder="https://aluno.serneuropsi.com.br/…"></label>
      <label class="field">Teste relacionado<input id="f_vtest" list="f_vtests" value="${NS.esc(v.test || '')}"><datalist id="f_vtests">${tests}</datalist></label>
      <label class="field">Ordem<input id="f_vsort" type="number" value="${v.sort ?? 0}"></label>
      <label class="field span-2">Descrição (opcional)<textarea id="f_vdesc" rows="3">${NS.esc(v.description || '')}</textarea></label>`;
  }
  const videoPayload = () => ({
    title: $('#f_vtitle').value.trim(), url: $('#f_vurl').value.trim(), test: $('#f_vtest').value.trim(),
    description: $('#f_vdesc').value.trim(), sort: Number($('#f_vsort').value) || 0,
  });
  $('#videoSearch')?.addEventListener('input', renderVideos);
  $('#videoFilter')?.addEventListener('click', (e) => {
    const b = e.target.closest('[data-vf]'); if (!b) return;
    state.videoFilter = b.dataset.vf;
    $$('#videoFilter .seg-btn').forEach(x => x.classList.toggle('active', x === b));
    renderVideos();
  });
  $('#videoNewBtn')?.addEventListener('click', () => openEdit('Novo vídeo', videoForm(), async () => {
    await NS.api('/api/admin/videos', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(videoPayload()) });
    loadVideos();
  }));
  $('#videoGrid')?.addEventListener('click', async (e) => {
    const ed = e.target.closest('[data-edit-video]'), del = e.target.closest('[data-del-video]');
    if (ed) {
      const v = (state.videos || []).find(x => x.id === ed.dataset.editVideo); if (!v) return;
      openEdit('Editar vídeo', videoForm(v), async () => {
        await NS.api('/api/admin/videos/' + v.id, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(videoPayload()) });
        loadVideos();
      });
    }
    if (del) {
      if (!confirm('Excluir este vídeo da lista?')) return;
      try { await NS.api('/api/admin/videos/' + del.dataset.delVideo, { method: 'DELETE' }); loadVideos(); NS.toast('Vídeo excluído.'); }
      catch (err) { NS.toast(err.message, true); }
    }
  });

  // ---------------- Modal genérico de edição ----------------
  let editSaver = null;
  function openEdit(title, formHtml, onSave) {
    $('#editTitle').textContent = title;
    $('#editBody').innerHTML = `<div class="form-grid">${formHtml}</div><span id="editMsg" class="inline-msg"></span>`;
    editSaver = onSave;
    $('#editSave').style.display = onSave ? '' : 'none';
    $('#editModal').hidden = false;
  }
  $('#editClose')?.addEventListener('click', () => { $('#editModal').hidden = true; });
  $('#editModal')?.addEventListener('click', (e) => { if (e.target.id === 'editModal') $('#editModal').hidden = true; });
  $('#editSave')?.addEventListener('click', async () => {
    if (!editSaver) return;
    $('#editSave').disabled = true;
    try { await editSaver(); $('#editModal').hidden = true; NS.toast('Salvo.'); }
    catch (e) { const m = $('#editMsg'); if (m) { m.textContent = e.message; m.className = 'inline-msg err'; } }
    finally { $('#editSave').disabled = false; }
  });

  const VIEW_LOADERS = {
    dashboard: loadDashboard, pacientes: loadPatients, planos: loadPlanos,
    admin: loadAdmin, conta: fillConta, videos: loadVideos, realizados: loadRealizados,
    geracao: () => window.glOnShow && window.glOnShow(),
  };

  // ---------------- Cores do site (definidas pelo admin) ----------------
  function applySiteColors(site) {
    const c = (site && site.colors) || {};
    const root = document.documentElement.style;
    if (c.primary) {
      root.setProperty('--primary', c.primary);
      root.setProperty('--primary-ink', `color-mix(in srgb, ${c.primary} 84%, #000)`);
      root.setProperty('--primary-soft', `color-mix(in srgb, ${c.primary} 10%, var(--surface))`);
      root.setProperty('--primary-ring', `color-mix(in srgb, ${c.primary} 18%, transparent)`);
    }
    if (c.accent) root.setProperty('--cta', c.accent);
    if (c.secondary) root.setProperty('--brand-2', c.secondary);
    if (c.dark) root.setProperty('--dark', c.dark);
    if (site && site.whatsapp) { const w = $('#consultorBtn'); if (w) w.href = 'https://wa.me/' + site.whatsapp; }
  }
  fetch('/api/site').then(r => r.json()).then(({ site }) => { state.site = site || {}; applySiteColors(state.site); }).catch(() => {});

  // ---------------- Acesso: modo teste (trial) e bloqueio ----------------
  function applyAccess(acc) {
    acc = acc || {};
    state.blocked = acc.blocked || null;
    const banner = $('#trialBanner');
    if (acc.trial && !acc.blocked) {
      const d = acc.trial_days_left ?? 0;
      $('#trialDays').textContent = d;
      $('#trialTitle').textContent = d <= 1 ? 'Último dia do seu teste gratuito' : `Modo teste: faltam ${d} dias`;
      $('#trialSub').textContent = 'Ao fim do período o acesso é bloqueado. Adquira créditos para continuar sem interrupção.';
      banner.classList.toggle('urgent', d <= 3);
      banner.hidden = false;
    } else banner.hidden = true;
    if (acc.blocked === 'suspended') {
      $('#blockedTitle').textContent = 'Conta suspensa';
      $('#blockedText').textContent = 'Seu acesso foi suspenso pelo administrador. Entre em contato para reativar.';
      $('#blockedBuy').hidden = true;
    }
    if (acc.blocked) $('#blockedScreen').hidden = false;
  }
  window.NS = window.NS || {};
  window.NS.onBlocked = (kind) => { applyAccess({ blocked: kind }); };
  $('#blockedBuy')?.addEventListener('click', () => showView('planos'));
  $('#blockedLogout')?.addEventListener('click', () => $('#logoutBtn')?.click());

  // ---------------- Boot (chamado por app.js após auth) ----------------
  window.onSessionReady = async function () {
    // sem login: mostra tudo menos admin
    if (!state.authEnabled) {
      $('#sidebarUser').hidden = true;
    } else {
      try {
        const p = await NS.api('/api/profile');
        state.profile = p;
        const prefs = p.prefs || {};
        if (prefs.theme) applyTheme(prefs.theme);
        $('#prefEmail').checked = !!prefs.notify_email;
        $('#prefTasks').checked = !!prefs.notify_tasks;
        refreshIdentity();
        applyAccess(p.access);
      } catch (e) { console.error(e); }
      if (!state.blocked) NS.api('/api/patients').then(({ patients = [] }) => { state.patients = patients; }).catch(() => {});
    }
    // retorno do Mercado Pago
    const m = location.hash.match(/pago=([^&]+)/);
    if (m) {
      if (m[1] === '1') { NS.toast('Pagamento aprovado! Créditos serão liberados em instantes.'); setTimeout(refreshCredits, 4000); }
      else if (m[1] === 'pend') NS.toast('Pagamento pendente — os créditos entram após a confirmação.');
      else NS.toast('Pagamento não concluído.', true);
      history.replaceState(null, '', '#planos');
    }
    showView(location.hash.slice(1).split('?')[0] || 'dashboard');
  };
  window.NS = window.NS || {};
})();
