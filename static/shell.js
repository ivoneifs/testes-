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
  const VIEWS = ['dashboard', 'pacientes', 'historia', 'laudos', 'planos', 'config', 'admin', 'conta'];
  const TITLES = {
    dashboard: 'Dashboard', pacientes: 'Pacientes', historia: 'História de Vida',
    laudos: 'Laudos', planos: 'Planos e Recargas', config: 'Configurações',
    admin: 'Administração', conta: 'Minha Conta',
  };
  let currentView = null;

  function showView(name) {
    name = String(name || '').split('?')[0];
    if (!VIEWS.includes(name)) name = 'dashboard';
    if (name === 'admin' && state.profile?.role !== 'admin') name = 'dashboard';
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

  function refreshIdentity() {
    const p = state.profile || {};
    const roleEl = $('#userRole');
    if (roleEl) { roleEl.textContent = p.role === 'admin' ? 'Administrador' : 'Profissional'; roleEl.hidden = false; }
    $('#userEmail').textContent = p.full_name || p.email || state.user?.email || '';
    $('#navAdmin').hidden = p.role !== 'admin';
    const cc = $('#creditCard');
    if (cc) {
      $('#creditBalance').textContent = p.credits ?? 0;
      cc.hidden = p.role === 'admin';           // admin não usa créditos
    }
  }

  // ---------------- Dashboard ----------------
  async function loadDashboard() {
    try {
      const [{ evaluations = [] }, { patients = [] }] = await Promise.all([
        NS.api('/api/evaluations').catch(() => ({ evaluations: [] })),
        NS.api('/api/patients').catch(() => ({ patients: [] })),
      ]);
      $('#kpiEvals').textContent = evaluations.length;
      $('#kpiPatients').textContent = patients.length;
      $('#kpiCredits').textContent = state.profile?.credits ?? 0;
      $('#kpiTests').textContent = state.tests?.length ?? 62;
      $('#dashRecent').innerHTML = evaluations.slice(0, 8).map(ev => {
        const nm = NS.esc(ev.patient?.name || '(sem nome)');
        const when = new Date(ev.updated_at || ev.created_at).toLocaleString('pt-BR');
        const tests = (ev.tests || []).map(t => t.test).filter(Boolean).join(', ');
        return `<div class="list-row"><div><b>${nm}</b><small>${NS.esc(tests || 'sem testes')}</small></div><span class="muted small">${when}</span></div>`;
      }).join('') || '<p class="muted small">Nenhuma avaliação ainda.</p>';
    } catch (e) { NS.toast(e.message, true); }
  }

  // ---------------- Pacientes ----------------
  async function loadPatients() {
    const body = $('#patientsBody');
    try {
      const { patients = [] } = await NS.api('/api/patients');
      state.patients = patients;
      $('#patientOptions').innerHTML = patients.map(p => `<option value="${NS.esc(p.name)}">`).join('');
      body.innerHTML = patients.map(p => `<tr>
        <td>${NS.esc(p.name)}</td><td>${NS.esc(p.birth_date || '—')}</td>
        <td>${NS.esc(p.sex || '—')}</td><td>${NS.esc(p.education || '—')}</td>
        <td class="row-acts">
          <button class="btn ghost xs" data-use="${p.id}">Usar</button>
          <button class="btn ghost xs" data-edit-pat="${p.id}">Editar</button>
          <button class="btn ghost xs danger" data-del-pat="${p.id}">Excluir</button>
        </td></tr>`).join('') || '<tr><td colspan="5" class="muted small">Nenhum paciente cadastrado.</td></tr>';
    } catch (e) { body.innerHTML = `<tr><td colspan="5" class="inline-msg err">${NS.esc(e.message)}</td></tr>`; }
  }
  $('#patientNewBtn')?.addEventListener('click', () => patientForm());
  $('#patientsBody')?.addEventListener('click', async (e) => {
    const t = e.target;
    if (t.dataset.editPat) return patientForm(state.patients.find(p => p.id === t.dataset.editPat));
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
  function patientForm(p) {
    p = p || {};
    openEdit(p.id ? 'Editar paciente' : 'Novo paciente', `
      <label class="field span-2">Nome<input id="f_name" value="${NS.esc(p.name || '')}"></label>
      <label class="field">Nascimento<input id="f_birth" type="date" value="${NS.esc(p.birth_date || '')}"></label>
      <label class="field">Sexo<select id="f_sex"><option value="">—</option>
        <option${p.sex === 'Feminino' ? ' selected' : ''}>Feminino</option>
        <option${p.sex === 'Masculino' ? ' selected' : ''}>Masculino</option></select></label>
      <label class="field span-2">Escolaridade<input id="f_edu" value="${NS.esc(p.education || '')}"></label>
      <label class="field span-2">Notas<textarea id="f_notes" rows="2">${NS.esc(p.notes || '')}</textarea></label>`,
      async () => {
        const body = {
          name: $('#f_name').value.trim(), birth_date: $('#f_birth').value || null,
          sex: $('#f_sex').value || null, education: $('#f_edu').value.trim() || null,
          notes: $('#f_notes').value.trim() || null,
        };
        if (!body.name) throw new Error('Informe o nome.');
        const url = p.id ? '/api/patients/' + p.id : '/api/patients';
        await NS.api(url, { method: p.id ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        loadPatients();
      });
  }

  // ---------------- Planos ----------------
  const PACKS = [
    { key: 'inicial', nome: 'Pack Inicial', preco: 'R$ 49', unid: '/ pacote', laudos: '5 Laudos', desc: 'Ideal para quem está começando.', tag: '', itens: ['Suporte via e-mail', 'Exportação em PDF', 'IA para laudos'] },
    { key: 'profissional', nome: 'Pack Profissional', preco: 'R$ 149', unid: '/ pacote', laudos: '20 Laudos', desc: 'O melhor custo-benefício para sua clínica.', tag: 'Mais vendido', itens: ['Prioridade na fila', 'Suporte WhatsApp', 'História de Vida ilimitada', '20 créditos de laudo'] },
    { key: 'premium', nome: 'Pack Clínica Premium', preco: 'R$ 299', unid: '/ pacote', laudos: '50 Laudos', desc: 'Para alta demanda e grandes fluxos.', tag: '', itens: ['Consultoria VIP', 'Treinamento de equipe', 'Cota alta de créditos', 'Personalização de layout'] },
  ];
  function loadPlanos() {
    $('#planosGrid').innerHTML = PACKS.map(p => `
      <div class="plano${p.tag ? ' plano--feat' : ''}">
        ${p.tag ? `<span class="plano-tag">${p.tag}</span>` : ''}
        <h3>${p.nome}</h3>
        <div class="plano-price">${p.preco}<span>${p.unid}</span></div>
        <div class="plano-laudos">${p.laudos}</div>
        <p class="muted small">${p.desc}</p>
        <ul>${p.itens.map(i => `<li>${i}</li>`).join('')}</ul>
        <button class="btn primary" data-buy="${p.key}">Comprar agora</button>
      </div>`).join('');
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
    const body = $('#prosBody');
    try {
      const { professionals = [] } = await NS.api('/api/admin/professionals');
      state.pros = professionals;
      renderPros();
    } catch (e) { body.innerHTML = `<tr><td colspan="8" class="inline-msg err">${NS.esc(e.message)}</td></tr>`; }
  }
  function renderPros() {
    const q = ($('#proSearch').value || '').toLowerCase();
    const rows = (state.pros || []).filter(p =>
      !q || (p.full_name || '').toLowerCase().includes(q) || (p.email || '').toLowerCase().includes(q));
    $('#prosBody').innerHTML = rows.map(p => `<tr>
      <td>${NS.esc(p.full_name || '—')}</td><td>${NS.esc(p.email || '—')}</td>
      <td>${NS.esc(p.professional_id || '—')}</td>
      <td><span class="pill${p.role === 'admin' ? ' pill--admin' : ''}">${p.role === 'admin' ? 'Admin' : 'Profissional'}</span></td>
      <td><span class="pill${p.status === 'suspended' ? ' pill--off' : ' pill--ok'}">${p.status === 'suspended' ? 'Suspenso' : 'Ativo'}</span></td>
      <td>${NS.esc(p.plan || '—')}</td><td>${p.credits ?? 0}</td>
      <td class="row-acts">
        <button class="btn ghost xs" data-edit-pro="${p.id}">Editar</button>
        <button class="btn ghost xs danger" data-del-pro="${p.id}">Excluir</button>
      </td></tr>`).join('') || '<tr><td colspan="8" class="muted small">Nenhum profissional.</td></tr>';
  }
  $('#proSearch')?.addEventListener('input', renderPros);
  $('#prosBody')?.addEventListener('click', async (e) => {
    const t = e.target;
    if (t.dataset.editPro) {
      const p = state.pros.find(x => x.id === t.dataset.editPro); if (!p) return;
      openEdit('Editar profissional', `
        <label class="field span-2">Nome<input id="f_fn" value="${NS.esc(p.full_name || '')}"></label>
        <label class="field">CRP<input id="f_crp" value="${NS.esc(p.professional_id || '')}"></label>
        <label class="field">Papel<select id="f_role">
          <option value="professional"${p.role !== 'admin' ? ' selected' : ''}>Profissional</option>
          <option value="admin"${p.role === 'admin' ? ' selected' : ''}>Administrador</option></select></label>
        <label class="field">Status<select id="f_status">
          <option value="active"${p.status !== 'suspended' ? ' selected' : ''}>Ativo</option>
          <option value="suspended"${p.status === 'suspended' ? ' selected' : ''}>Suspenso</option></select></label>
        <label class="field">Plano<input id="f_plan" value="${NS.esc(p.plan || '')}"></label>
        <label class="field">Créditos<input id="f_credits" type="number" value="${p.credits ?? 0}"></label>`,
        async () => {
          await NS.api('/api/admin/professionals/' + p.id, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              full_name: $('#f_fn').value.trim(), professional_id: $('#f_crp').value.trim(),
              role: $('#f_role').value, status: $('#f_status').value,
              plan: $('#f_plan').value.trim() || null, credits: Number($('#f_credits').value) || 0,
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

  // ---------------- Modal genérico de edição ----------------
  let editSaver = null;
  function openEdit(title, formHtml, onSave) {
    $('#editTitle').textContent = title;
    $('#editBody').innerHTML = `<div class="form-grid">${formHtml}</div><span id="editMsg" class="inline-msg"></span>`;
    editSaver = onSave;
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
    admin: loadAdmin, conta: fillConta,
  };

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
      } catch (e) { console.error(e); }
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
