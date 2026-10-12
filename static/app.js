/*
  NeuroScore - interface da planilha web.
  O navegador envia apenas pontos brutos e dados do paciente ao servidor local.
  As fórmulas e normas permanecem no banco derivado da planilha Excel original.
*/
const $ = (s) => document.querySelector(s);
const state = {
  tests: [], meta: null, result: null, results: [], anamnesis: null,
  testReports: [], integrated: null, laudoModel: null, openaiConfigured: false,
  authEnabled: false, token: '', user: null, evalId: null, sb: null,
  externalTests: [],
};

const els = {
  list: $('#testList'), search: $('#testSearch'), title: $('#laudosTestTitle'), raw: $('#rawFields'),
  params: $('#parameterFields'), paramsPanel: $('#parametersPanel'), count: $('#fieldCount'), inputMode: $('#inputMode'),
  calc: $('#calculateBtn'), clear: $('#clearBtn'), results: $('#resultsSection'),
  tables: $('#resultTables'), charts: $('#chartGrid'), toast: $('#toast'),
  testReportBtn: $('#testReportBtn'), testReportOutput: $('#testReportOutput'),
  files: $('#anamnesisFiles'), fileList: $('#fileList'), analyzeBtn: $('#analyzeAnamnesisBtn'),
  anamnesisOutput: $('#anamnesisOutput'), anamnesisAlert: $('#anamnesisAlert'),
  modelFiles: $('#laudoModelFiles'), modelFileList: $('#modelFileList'), analyzeModelBtn: $('#analyzeModelBtn'),
  modelOutput: $('#modelOutput'), modelAlert: $('#modelAlert'),
  integratedBtn: $('#integratedBtn'), integratedOutput: $('#integratedOutput'),
  laudoActions: $('#laudoActions'), saveLaudoBtn: $('#saveLaudoBtn'), printLaudoBtn: $('#printLaudoBtn'),
  docxBtn: $('#docxBtn'), docxBtn2: $('#docxBtn2'),
  externalList: $('#externalList'),
};

// ---------- Outros instrumentos (corrigidos fora do sistema) ----------
function renderExternal(){
  els.externalList.innerHTML=state.externalTests.map((t,i)=>`
    <div class="external-item" data-ext="${i}">
      <div class="external-head">
        <input class="ext-name" data-k="nome" value="${esc(t.nome||'')}" placeholder="Nome do instrumento" />
        <label class="btn ghost xs ext-up">📎 Anexar correção
          <input type="file" data-ext-file="${i}" accept="application/pdf,image/*,.txt,.csv" multiple hidden />
        </label>
        <button type="button" class="btn ghost xs danger" data-ext-del="${i}">Remover</button>
      </div>
      <div class="ext-status ${/^(⚠|Falha)/.test(t._status||'')?'inline-msg err':'muted small'}" data-ext-status="${i}">${esc(t._status||'')}</div>
      <textarea class="ext-res" data-k="resultados" rows="3" placeholder="Resultados corrigidos (escores, percentis, classificações…). Ou anexe o relatório já corrigido do SON-R / TAVIS / Perfil Sensorial 2.">${esc(t.resultados||'')}</textarea>
      <textarea class="ext-obs" data-k="observacoes" rows="2" placeholder="Observações / interpretação (opcional)">${esc(t.observacoes||'')}</textarea>
    </div>`).join('');
}
els.externalList?.addEventListener('change',async e=>{
  const inp=e.target.closest('[data-ext-file]'); if(!inp||!inp.files.length) return;
  const i=+inp.dataset.extFile, t=state.externalTests[i]; if(!t) return;
  const st=els.externalList.querySelector(`[data-ext-status="${i}"]`);
  if(st){ st.textContent='Lendo o documento…'; }
  try{
    const fd=new FormData(); fd.append('nome',t.nome||'');
    [...inp.files].forEach(f=>fd.append('files',f));
    const r=await api('/api/ai/external-instrument',{method:'POST',body:fd});
    if(r.instrumento && !t.nome) t.nome=r.instrumento;
    if(r.tipo_documento==='protocolo_sem_correcao'){
      t._status='⚠ Parece um protocolo SEM correção. A IA não pontua testes — corrija no software/manual oficial e anexe o relatório pronto.';
    }else{
      t.resultados=[t.resultados,r.resultados].filter(Boolean).join('\n').trim();
      t.observacoes=[t.observacoes,r.observacoes].filter(Boolean).join('\n').trim();
      const al=(r.alertas||[]).join(' · ');
      t._status='✓ Transcrito do documento.'+(al?' Alertas: '+al:'');
    }
  }catch(err){ t._status='Falha: '+err.message; }
  finally{ inp.value=''; renderExternal(); }
});
els.externalList?.addEventListener('input',e=>{
  const item=e.target.closest('[data-ext]'); if(!item) return;
  const i=+item.dataset.ext, k=e.target.dataset.k;
  if(state.externalTests[i]) state.externalTests[i][k]=e.target.value;
});
els.externalList?.addEventListener('click',e=>{
  const b=e.target.closest('[data-ext-del]'); if(!b) return;
  state.externalTests.splice(+b.dataset.extDel,1); renderExternal();
});
document.querySelector('#externalCard')?.addEventListener('click',e=>{
  const b=e.target.closest('[data-ext-preset]'); if(!b) return;
  state.externalTests.push({nome:b.dataset.extPreset||'',resultados:'',observacoes:''});
  renderExternal();
  els.externalList.querySelector('.external-item:last-child .ext-name')?.focus();
});
function collectExternal(){
  return state.externalTests
    .map(t=>({nome:(t.nome||'').trim(),resultados:(t.resultados||'').trim(),observacoes:(t.observacoes||'').trim()}))
    .filter(t=>t.nome && (t.resultados || t.observacoes));
}

function toast(msg, error=false){
  els.toast.textContent = msg; els.toast.className = `toast show${error?' error':''}`;
  clearTimeout(window.__toastTimer); window.__toastTimer=setTimeout(()=>els.toast.className='toast',3200);
}
function esc(v=''){return String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
function parseNum(v){ if(typeof v==='number' && Number.isFinite(v)) return v; if(typeof v==='string' && /^-?\d+(?:[.,]\d+)?$/.test(v.trim())) return Number(v.replace(',','.')); return null; }

// Calcula idade cronológica apenas para exibição; a correção usa as datas dentro da lógica da planilha.
function patient(){
  return {name:$('#patientName').value.trim(),birth_date:$('#birthDate').value,application_date:$('#applicationDate').value,sex:$('#sex').value,education:$('#education').value.trim()};
}
function updateAge(){
  const p=patient(); if(!p.birth_date||!p.application_date){$('#ageChip').textContent='Idade: —';return;}
  const b=new Date(`${p.birth_date}T12:00:00`), a=new Date(`${p.application_date}T12:00:00`); if(a<b){$('#ageChip').textContent='Datas inválidas';return;}
  let y=a.getFullYear()-b.getFullYear(), m=a.getMonth()-b.getMonth(), d=a.getDate()-b.getDate();
  if(d<0){m--; const prev=new Date(a.getFullYear(),a.getMonth(),0); d+=prev.getDate();} if(m<0){y--;m+=12;}
  $('#ageChip').textContent=`Idade: ${y}a ${m}m ${d}d`;
}
['birthDate','applicationDate'].forEach(id=>$(`#${id}`).addEventListener('change',updateAge));
// História de Vida usa o mesmo paciente do corretor (campos espelhados)
function syncHv(){const n=$('#hvName'),b=$('#hvBirth');if(n)n.value=$('#patientName').value;if(b)b.value=$('#birthDate').value;}
[['hvName','patientName'],['hvBirth','birthDate']].forEach(([a,b])=>{
  $(`#${a}`)?.addEventListener('input',()=>{$(`#${b}`).value=$(`#${a}`).value;if(b==='birthDate')updateAge();});
  $(`#${b}`)?.addEventListener('input',syncHv); $(`#${b}`)?.addEventListener('change',syncHv);
});

async function api(url, options={}){
  const opt={...options, headers:{...(options.headers||{})}};
  if(state.token) opt.headers['Authorization']=`Bearer ${state.token}`;
  const r=await fetch(url,opt); let data; try{data=await r.json();}catch{data={detail:await r.text()};}
  if(r.status===401 && state.authEnabled){ location.replace('/login.html'); throw new Error('Sessão expirada.'); }
  if(r.status===402){ setTimeout(()=>{ try{ window.showView ? window.showView('planos') : (location.hash='#planos'); }catch{} },1200); }
  if(r.status===403 && /^(trial_expired|suspended)/.test(data.detail||'')){ window.NS?.onBlocked?.(data.detail.split(':')[0]); }
  if(!r.ok) throw new Error(data.detail || `HTTP ${r.status}`); return data;
}

// ---------- Autenticação (Supabase) ----------
async function bootstrapAuth(){
  let cfg={};
  try{ cfg=await (await fetch('/api/config')).json(); }catch{}
  state.authEnabled=!!cfg.auth_enabled;
  if(!state.authEnabled) return true;
  if(!window.supabase){ toast('Não foi possível carregar o login.',true); return false; }
  state.sb=window.supabase.createClient(cfg.supabase_url,cfg.supabase_anon_key);
  const {data:{session}}=await state.sb.auth.getSession();
  if(!session){ location.replace('/login.html'); return false; }
  state.token=session.access_token;
  state.user={id:session.user.id,email:session.user.email};
  state.sb.auth.onAuthStateChange((_e,s)=>{
    if(!s){ location.replace('/login.html'); return; }
    state.token=s.access_token;
  });
  const su=$('#sidebarUser'); if(su){ su.hidden=false; $('#userEmail').textContent=state.user.email; }
  $('#saveEvalBtn').hidden=false; $('#myEvalsBtn').hidden=false;
  return true;
}
$('#logoutBtn')?.addEventListener('click',async()=>{
  try{ await state.sb?.auth.signOut(); }finally{ location.replace('/login.html'); }
});

async function init(){
  const now=new Date(); $('#applicationDate').value=`${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`; updateAge();
  if(!(await bootstrapAuth())) return;
  try{
    const health=await api('/api/health'); state.openaiConfigured=health.openai_configured;
    $('#apiDot').className='status-dot ok'; $('#apiStatus').textContent=`${health.tests} instrumentos • IA ${health.openai_configured?'configurada':'sem chave'}`; $('#aiConfigNote').hidden=health.openai_configured;
    const data=await api('/api/tests'); state.tests=data.tests; renderTestList(); renderArchive();
  }catch(e){$('#apiDot').className='status-dot bad';$('#apiStatus').textContent='Servidor indisponível';toast(e.message,true);}
  try{ if(typeof window.onSessionReady==='function') await window.onSessionReady(); }catch(e){ console.error('shell',e); }
}
// helpers reaproveitados pelo shell
window.NS = { api, toast, state, esc, get sb(){return state.sb;} };
window.loadEvaluation = (ev)=>loadEvaluation(ev);
// Instrumentos com "formas" (uma entrada na lista, seletor de forma dentro do teste).
const TEST_GROUPS=[{label:'Perfil Sensorial 2',prefix:'Perfil Sensorial 2 - ',chart:'sensory_profile'}];
// Nomes de exibição de abas com nome técnico na planilha.
const TEST_LABELS={'Vin_3_Ext_Ent':'Vineland-3 · Entrevista (item a item)','Vin_3_Ext_Pais':'Vineland-3 · Pais/Cuidadores (item a item)'};
function testLabel(name){return TEST_LABELS[name]||name;}
function testGroupOf(name){return TEST_GROUPS.find(g=>name===g.label||name.startsWith(g.prefix));}
function renderTestList(){
  const q=els.search.value.trim().toLowerCase();
  const seen=new Set(); const items=[];
  for(const t of state.tests){
    const g=testGroupOf(t.name);
    const disp=g?g.label:t.name, chart=g?g.chart:(t.chart_type||''), shown=testLabel(disp);
    if(g){ if(seen.has(g.label))continue; seen.add(g.label); }
    if(!disp.toLowerCase().includes(q) && !shown.toLowerCase().includes(q)) continue;
    const active=g?(state.meta?.name||'').startsWith(g.prefix):state.meta?.name===t.name;
    items.push(`<button class="test-item ${active?'active':''}" data-test="${esc(disp)}"><span>${esc(shown)}</span><small>${esc(chart)}</small></button>`);
  }
  els.list.innerHTML=items.join('');
  els.list.querySelectorAll('.test-item').forEach(b=>b.addEventListener('click',()=>selectTest(b.dataset.test)));
}
const PS_FORMS=['Criança','Criança Pequena','Bebê','Professor','Abreviado','Consolidado'];
function renderPsFormRow(currentFull){
  const row=$('#psFormRow'), sel=$('#psFormSelect');
  const forms=PS_FORMS.filter(f=>state.tests.some(t=>t.name==='Perfil Sensorial 2 - '+f));
  sel.innerHTML=forms.map(f=>`<option value="Perfil Sensorial 2 - ${esc(f)}"${('Perfil Sensorial 2 - '+f)===currentFull?' selected':''}>${esc(f)}</option>`).join('');
  row.hidden=false;
}
els.search.addEventListener('input',renderTestList);
$('#menuBtn').addEventListener('click',()=>$('#sidebar').classList.toggle('open'));

async function selectTest(name){
  const g=testGroupOf(name);
  let full=name;
  if(g){
    // "Perfil Sensorial 2" (grupo) -> abre a forma atual ou a primeira disponível.
    if(name===g.label){
      const cur=(state.meta?.name||'').startsWith(g.prefix)?state.meta.name:null;
      full=cur||(PS_FORMS.map(f=>g.prefix+f).find(n=>state.tests.some(t=>t.name===n)));
      if(!full){toast('Nenhuma forma disponível.',true);return;}
    }
    renderPsFormRow(full);
  }else{
    $('#psFormRow').hidden=true;
  }
  els.title.textContent=g?g.label:testLabel(full); els.raw.innerHTML=''; $('#testLoading').hidden=false; $('#testLoading').textContent='Preparando campos e fórmulas…'; els.calc.disabled=true;
  try{
    state.meta=await api(`/api/tests/${encodeURIComponent(full)}`); state.result=null; renderTestList(); renderInputs(); renderArchive();
    $('#sidebar').classList.remove('open');
  }catch(e){$('#testLoading').textContent='Não foi possível preparar este teste.';toast(e.message,true);}
}
$('#psFormSelect')?.addEventListener('change',e=>{ if(e.target.value) selectTest(e.target.value); });
function groupFields(fields){
  const groups=[]; let current=[]; let prev=null;
  for(const f of fields){const m=f.cell.match(/\d+$/);const row=m?Number(m[0]):0;if(prev!==null && row-prev>8 && current.length){groups.push(current);current=[];}current.push(f);prev=row;}
  if(current.length)groups.push(current);return groups;
}
const INPUT_MODE_LABEL={pontos_brutos:'Somente PB',itens:'Item a item',campos_origem:'Entrada original'};
function renderInputs(){
  const m=state.meta; $('#testLoading').hidden=true; els.count.textContent=`${m.raw_fields.length} campos`;
  const hidden=(m.detail_fields||[]).length; els.inputMode.textContent=INPUT_MODE_LABEL[m.input_mode]||'Entrada original';
  els.inputMode.title=hidden?`${hidden} campos de itens/origem mantidos fora da entrada compacta`:'';
  const noteEl=$('#testNote'); if(noteEl){ noteEl.textContent=m.note||''; noteEl.hidden=!m.note; }
  const bySection=m.input_mode==='itens' && m.raw_fields.some(f=>f.ps_section||f.group||f.source==='ps-item-extra');
  let groups, titles;
  if(bySection){
    const map=new Map();
    for(const f of m.raw_fields){const k=f.ps_section||f.group||'Itens avulsos';if(!map.has(k))map.set(k,[]);map.get(k).push(f);}
    groups=[...map.values()]; titles=[...map.keys()];
  }else{
    const pc=m.item_protocol?new Set(protoCells(m.item_protocol)):null;
    groups=groupFields(pc?m.raw_fields.filter(f=>!pc.has(f.cell)):m.raw_fields).filter(g=>g.length); titles=null;
  }
  els.raw.innerHTML=groups.map((g,i)=>{
    const auto=!bySection && g.every(f=>f.allow_override_formula);
    const title=titles?titles[i]:(auto
      ? 'Calculado pela planilha — digite um valor apenas se quiser sobrepor'
      : (groups.length>1?`Bloco ${i+1}`:'Entrada rápida'));
    const cells=g.map(f=>{
      const calc=!!f.allow_override_formula;
      const item=f.source==='ps-item'||f.source==='ps-item-extra'||f.source==='scale-item';
      const prefill=(!calc && !item && typeof f.current==='number')?f.current:'';
      const lab=(item && /·/.test(f.label))?esc(f.label.replace(/^[^·]*·\s*/,'')):esc(f.label);
      const rg=Array.isArray(f.range)?f.range:(item?[0,5]:null);
      const ph=calc?'auto':(rg?`${rg[0]}–${rg[1]}`:'PB');
      // Itens com poucas opções (Perfil Sensorial 0–5, escalas 0–2/0–3): botões de toque que
      // só preenchem o mesmo campo numérico — a correção continua lendo o input.
      const chips=item && rg && rg[1]-rg[0]<=6 && Number.isInteger(rg[0]) && Number.isInteger(rg[1]);
      const seg=chips?`<div class="score-seg" role="group" aria-label="${lab}">`
        +Array.from({length:rg[1]-rg[0]+1},(_,k)=>rg[0]+k).map(v=>`<button type="button" data-set="${v}">${v}</button>`).join('')
        +`</div>`:'';
      return `<div class="raw-field${calc?' raw-field--auto':''}${chips?' raw-field--chips':''}">`
        +`<label>${lab} <span class="cell-ref">${esc(f.cell)}</span></label>`+seg
        +`<input data-raw="${esc(f.cell)}"${calc?' data-calc="1"':''} inputmode="decimal" type="number" step="any"`
        +`${rg?` min="${rg[0]}" max="${rg[1]}"`:''} value="${prefill}" placeholder="${ph}"`
        +`${calc?' title="A planilha calcula este campo sozinha. Digite um valor para sobrepor."':''} /></div>`;
    }).join('');
    const prog=bySection?` <span class="sec-prog" data-prog>0/${g.length}</span>`:'';
    return `<section class="raw-section${auto?' raw-section--auto':''}"><div class="raw-section-title">${esc(title)}${prog}</div><div class="raw-grid">${cells}</div></section>`;
  }).join('');
  els.raw.querySelectorAll('.raw-section').forEach(syncSection);
  if(m.item_protocol){
    const rest=els.raw.innerHTML;
    els.raw.innerHTML=protocolHtml(m.item_protocol)
      +(rest.trim()?`<details class="ravlt-manual"><summary>Ou digite só os pontos brutos / outros campos da planilha (opcional)</summary>${rest}</details>`:'');
    protoSetInformant(0);
  }
  if(m.vineland){
    els.raw.innerHTML=vinHtml(m.vineland)
      +`<details class="ravlt-manual"><summary>Ou digite só os pontos brutos de cada subdomínio (opcional)</summary>${els.raw.innerHTML}</details>`;
    vinSync();
  }
  if(m.answer_sheet){
    els.raw.innerHTML=ravltSheetHtml(m.answer_sheet)
      +`<details class="ravlt-manual"><summary>Ou digite só os totais de cada tentativa (opcional)</summary>${els.raw.innerHTML}</details>`;
  }
  const params=m.parameters||[]; els.paramsPanel.hidden=!params.length;
  const keepParam=m.input_mode!=='itens';
  els.params.innerHTML=params.map(p=>p.options
    // seletor da planilha (tabela normativa, amostra…): lista com as opções que ela aceita
    ? `<label class="field">${esc(p.label)}<select data-param="${esc(p.cell)}"><option value="">Selecione…</option>${p.options.map(o=>`<option${o===p.current?' selected':''}>${esc(o)}</option>`).join('')}</select></label>`
    : `<label class="field">${esc(p.label)}<input data-param="${esc(p.cell)}" value="${keepParam?esc(p.current??''):''}" /></label>`).join('');
  // tabela normativa fica visível (aberta) quando existir
  if(params.some(p=>p.selector)) els.paramsPanel.open=true;
  els.calc.disabled=!m.raw_fields.length; els.results.hidden=true; els.testReportBtn.disabled=true;
}
// Campos [data-calc] (somas/índices/totais com fórmula) são calculados pela
// planilha por padrão e só são enviados quando a pessoa digita um valor (override).
// Ao digitar, o campo é marcado com data-touched; ao esvaziar, volta a ser automático.
// ---------- Protocolo item a item (lido da planilha; ela pontua) ----------
function protoCells(p){return p.items.flatMap(i=>i.cells).concat((p.informant_cells||[]).filter(Boolean));}
function protocolHtml(p){
  const multi=p.informants>1;
  const inf=multi?`<div class="proto-inf"><span class="muted small">Respondente:</span><div class="seg" id="protoInf">${p.informant_names.map((n,k)=>
      `<button type="button" class="seg-btn${k?'':' active'}" data-inf="${k}">${esc(n)}</button>`).join('')}</div></div>`:'';
  const ids=(p.informant_cells||[]).map((c,k)=>c?`<label class="field proto-id" data-inf-id="${k}"${k?' hidden':''}>Identificação do respondente (nome / disciplina / parentesco)
      <input type="text" data-raw="${esc(c)}" data-text placeholder="obrigatório para a planilha calcular os fatores"></label>`:'').join('');
  let html='', sec=null;
  p.items.forEach((it,ix)=>{
    if(it.section!==sec){ if(sec!==null) html+='</div></section>'; sec=it.section;
      html+=`<section class="raw-section proto-sec"><div class="raw-section-title">${esc(sec||'Itens')} <span class="sec-prog" data-prog>0/0</span></div><div class="proto-items">`; }
    html+=`<div class="proto-item"><div class="proto-label">${esc(it.label)}</div>`
      +it.cells.map((c,k)=>`<div class="score-seg proto-seg" data-inf-row="${k}"${k?' hidden':''}>${it.options.map(o=>`<button type="button" data-pset="${esc(o)}">${esc(o)}</button>`).join('')}</div>`
        +`<input type="hidden" data-raw="${esc(c)}" data-text data-inf-cell="${k}">`).join('')
      +`</div>`;
  });
  if(sec!==null) html+='</div></section>';
  return `<section class="proto"><div class="ravlt-head"><b>Protocolo — item a item</b><span class="muted small">Toque na resposta de cada item. Toque de novo para limpar. A planilha pontua (inclusive itens invertidos).</span></div>${inf}${ids}${html}</section>`;
}
function protoSetInformant(k){
  state.protoInf=k;
  els.raw.querySelectorAll('[data-inf]').forEach(b=>b.classList.toggle('active',Number(b.dataset.inf)===k));
  els.raw.querySelectorAll('[data-inf-row]').forEach(x=>{x.hidden=Number(x.dataset.infRow)!==k;});
  els.raw.querySelectorAll('[data-inf-id]').forEach(x=>{x.hidden=Number(x.dataset.infId)!==k;});
  protoProgress();
}
function protoProgress(){
  const k=state.protoInf||0;
  els.raw.querySelectorAll('.proto-sec').forEach(sec=>{
    const ins=[...sec.querySelectorAll(`[data-inf-cell="${k}"]`)], n=ins.filter(i=>i.value!=='').length;
    const p=sec.querySelector('[data-prog]'); if(p){p.textContent=`${n}/${ins.length}`;p.classList.toggle('done',ins.length&&n===ins.length);}
  });
}
function protoSync(){
  els.raw.querySelectorAll('.proto-seg').forEach(seg=>{
    const inp=seg.parentElement.querySelector(`[data-inf-cell="${seg.dataset.infRow}"]`);
    seg.querySelectorAll('button').forEach(b=>b.classList.toggle('on',inp.value!==''&&b.dataset.pset===inp.value));
  });
  protoProgress();
}
els.raw.addEventListener('click',e=>{
  const inf=e.target.closest('[data-inf]'); if(inf){protoSetInformant(Number(inf.dataset.inf));return;}
  const b=e.target.closest('[data-pset]'); if(!b) return;
  const seg=b.parentElement, inp=seg.parentElement.querySelector(`[data-inf-cell="${seg.dataset.infRow}"]`);
  inp.value=inp.value===b.dataset.pset?'':b.dataset.pset; protoSync();
});

// ---------- Vineland-3: itens só pelo número (o texto é do protocolo impresso) ----------
// Cada toque grava 2/1/0 em vin:<sub>:<n> (e "Est" em vin:<sub>:<n>e). A tela aplica
// basal (4 seguidos com 2) e teto (4 seguidos com 0), soma e grava o bruto na célula
// do subdomínio; quem corrige é a planilha.
const VIN_P='vin:';
function vinAge(){
  const b=$('#birthDate').value, a=$('#applicationDate').value; if(!b||!a) return null;
  const B=new Date(b+'T00:00'), A=new Date(a+'T00:00'); let y=A.getFullYear()-B.getFullYear();
  if(A.getMonth()<B.getMonth()||(A.getMonth()===B.getMonth()&&A.getDate()<B.getDate())) y--;
  return y>=0?y:null;
}
function vinStart(sd,age){let it=1;for(const [a,i] of sd.inicio){if(age!==null&&age>=a)it=i;}return it;}
function vinItemHtml(key,n){
  const id=`${VIN_P}${key}:${n}`;
  return `<div class="vin-item" data-vin-item="${n}"><span class="vin-n">${n}</span>`
    +`<div class="score-seg vin-seg">${[2,1,0].map(v=>`<button type="button" data-vset="${v}">${v}</button>`).join('')}</div>`
    +`<button type="button" class="vin-est" data-vest title="Pontuação estimada">Est</button>`
    +`<input type="hidden" data-raw="${esc(id)}" data-text data-vin-val><input type="hidden" data-raw="${esc(id)}e" data-text data-vin-e></div>`;
}
function vinHtml(v){
  const sub=v.subdominios.map(sd=>`<section class="raw-section vin-sec" data-vin="${esc(sd.key)}" data-cell="${esc(sd.cell)}" data-n="${sd.itens}">
      <div class="raw-section-title"><span>${esc(sd.nome)} <small class="muted">· ${esc(sd.dominio)} · ${sd.itens} itens</small></span>
        <span class="vin-sum">Bruto: <b data-vin-raw>—</b></span></div>
      <div class="vin-status muted small" data-vin-status></div>
      <div class="vin-grid">${Array.from({length:sd.itens},(_,i)=>vinItemHtml(sd.key,i+1)).join('')}</div></section>`).join('');
  const mal=v.mal_adaptativo.map(md=>`<section class="raw-section vin-sec vin-mal" data-vin="${esc(md.key)}" data-cell="${esc(md.cell)}" data-n="${md.itens}" data-all="1">
      <div class="raw-section-title"><span>${esc(md.nome)} <small class="muted">· ${md.itens} itens · a partir de 3 anos · todos os itens</small></span>
        <span class="vin-sum">Bruto: <b data-vin-raw>—</b></span></div>
      <div class="vin-status muted small" data-vin-status></div>
      <div class="vin-grid">${Array.from({length:md.itens},(_,i)=>vinItemHtml(md.key,i+1)).join('')}</div></section>`).join('');
  const crit=`<section class="raw-section vin-sec vin-crit"><div class="raw-section-title"><span>Itens críticos <small class="muted">· 20 itens · 2 / 1 / 0 (não somam)</small></span></div>
      <div class="vin-grid">${v.criticos.map((c,i)=>`<div class="vin-item"><span class="vin-n">${i+1}</span><div class="score-seg vin-seg">${[2,1,0].map(x=>
        `<button type="button" data-vcrit="${x}">${x}</button>`).join('')}</div><input type="hidden" data-raw="${esc(c)}" data-vin-crit></div>`).join('')}</div></section>`;
  return `<section class="proto vin"><div class="ravlt-head"><b>Vineland-3 — ${esc(v.titulo)}</b>
    <span class="muted small">Leia cada pergunta no seu protocolo impresso e toque 2 / 1 / 0 no número do item (toque de novo para limpar). ${esc(v.regra)} Comece no item destacado para a idade.</span></div>
    <div class="vin-age muted small" data-vin-age></div>${sub}${mal}${crit}</section>`;
}
function vinCalc(vals,all){
  // vals[1..n] = null | 0 | 1 | 2. Devolve {raw, basal, teto, warn[]}
  const n=vals.length-1, warn=[];
  const answered=[]; for(let i=1;i<=n;i++) if(vals[i]!==null) answered.push(i);
  if(!answered.length) return {raw:null,warn};
  if(all){ let raw=0; for(let i=1;i<=n;i++) raw+=vals[i]||0; const b=n-answered.length; if(b) warn.push(`${b} em branco (contam 0)`); return {raw,warn}; }
  const run=(i,v)=>i+3<=n&&[0,1,2,3].every(k=>vals[i+k]===v);
  let teto=null; for(let i=1;i<=n;i++) if(run(i,0)){teto=i;break;}
  const lim=teto===null?n:teto-1;
  let basal=null; for(let i=1;i+3<=lim;i++) if(run(i,2)) basal=i;
  const lo=basal!==null?basal:1, hi=teto!==null?teto+3:n;
  if(basal===null && answered[0]>1) warn.push(`sem basal: aplique os itens anteriores ao ${answered[0]} até ter 4 seguidos com 2`);
  if(teto===null && answered[answered.length-1]<n) warn.push(`sem teto: continue até ter 4 seguidos com 0`);
  let raw=0, blank=0;
  for(let i=1;i<=n;i++){
    if(i<lo) raw+=2; else if(i>hi) raw+=0;
    else if(vals[i]===null) blank++; else raw+=vals[i];
  }
  if(blank && !warn.length) warn.push(`${blank} item(ns) em branco entre basal e teto (contam 0)`);
  return {raw,basal,teto,lo,hi,warn};
}
function vinSync(){
  const v=state.meta&&state.meta.vineland; if(!v) return;
  const age=vinAge(), ageEl=els.raw.querySelector('[data-vin-age]');
  if(ageEl) ageEl.textContent=age===null?'Informe nascimento e data de aplicação para destacar o item inicial de cada subdomínio.':`Idade: ${age} ano(s) — item inicial destacado em cada subdomínio.`;
  els.raw.querySelectorAll('.vin-sec[data-vin]').forEach(sec=>{
    const key=sec.dataset.vin, n=Number(sec.dataset.n), all=sec.dataset.all==='1';
    const sd=v.subdominios.find(x=>x.key===key);
    const vals=[null]; let est=0;
    sec.querySelectorAll('.vin-item').forEach(it=>{
      const iv=it.querySelector('[data-vin-val]'), ie=it.querySelector('[data-vin-e]');
      const val=iv.value===''?null:Number(iv.value); vals.push(val);
      it.querySelectorAll('[data-vset]').forEach(b=>b.classList.toggle('on',val!==null&&Number(b.dataset.vset)===val));
      const e=ie.value==='1'; it.querySelector('[data-vest]').classList.toggle('on',e); if(e&&val!==null) est++;
    });
    const start=sd?vinStart(sd,age):1;
    const r=vinCalc(vals,all);
    sec.querySelectorAll('.vin-item').forEach(it=>{
      const i=Number(it.dataset.vinItem);
      it.classList.toggle('vin-start',!all&&age!==null&&i===start);
      it.classList.toggle('vin-cred2',r.raw!==null&&!all&&r.lo!==undefined&&i<r.lo&&vals[i]===null);
      it.classList.toggle('vin-cred0',r.raw!==null&&!all&&r.hi!==undefined&&i>r.hi&&vals[i]===null);
    });
    const rawIn=els.raw.querySelector(`[data-raw="${sec.dataset.cell}"]:not([data-vin-val])`);
    if(rawIn){
      if(r.raw!==null){ rawIn.value=r.raw; rawIn.dataset.vinAuto='1'; }
      else if(rawIn.dataset.vinAuto==='1'){ rawIn.value=''; delete rawIn.dataset.vinAuto; }
    }
    sec.querySelector('[data-vin-raw]').textContent=r.raw===null?(rawIn&&rawIn.value!==''?rawIn.value+' (digitado)':'—'):r.raw;
    const st=[];
    if(sd&&age!==null&&age<sd.idade_min) st.push(`aplica-se a partir de ${sd.idade_min} anos`);
    if(!all&&age!==null) st.push(`início no item ${start}`);
    if(r.basal) st.push(`basal no item ${r.basal} (anteriores = 2)`);
    if(r.teto) st.push(`teto no item ${r.teto+3} (seguintes = 0)`);
    const answered=vals.filter(x=>x!==null).length;
    if(est&&answered) st.push(`Est: ${est} (${Math.round(100*est/answered)}% dos respondidos)`);
    const stEl=sec.querySelector('[data-vin-status]');
    stEl.innerHTML=st.map(esc).join(' · ')+(r.warn.length?`<div class="vin-warn">⚠ ${r.warn.map(esc).join(' · ')}</div>`:'');
  });
  els.raw.querySelectorAll('[data-vin-crit]').forEach(inp=>{
    inp.parentElement.querySelectorAll('[data-vcrit]').forEach(b=>b.classList.toggle('on',inp.value!==''&&Number(b.dataset.vcrit)===Number(inp.value)
      ||(inp.value===''&&inp.dataset.zero==='1'&&b.dataset.vcrit==='0')));
  });
}
els.raw.addEventListener('click',e=>{
  const b=e.target.closest('[data-vset],[data-vest],[data-vcrit]'); if(!b||!state.meta?.vineland) return;
  const it=b.closest('.vin-item');
  if('vset' in b.dataset){ const iv=it.querySelector('[data-vin-val]'); iv.value=iv.value===b.dataset.vset?'':b.dataset.vset; }
  else if('vest' in b.dataset){ const ie=it.querySelector('[data-vin-e]'); ie.value=ie.value==='1'?'':'1'; }
  else { // itens críticos: a planilha recebe 1 ou 2; 0 fica em branco (só marca na tela)
    const inp=it.querySelector('[data-vin-crit]'), v=b.dataset.vcrit;
    const cur=inp.value!==''?inp.value:(inp.dataset.zero==='1'?'0':'');
    const nxt=cur===v?'':v; inp.value=nxt==='0'?'':nxt; inp.dataset.zero=nxt==='0'?'1':'';
  }
  vinSync();
});
['birthDate','applicationDate'].forEach(id=>$(`#${id}`).addEventListener('change',()=>{ if(state.meta?.vineland) vinSync(); }));

// ---------- Ficha do RAVLT (igual à folha de respostas) ----------
// Cada toque numa palavra grava a ORDEM de evocação na célula da planilha; a
// planilha conta (COUNT), calcula efeitos, reconhecimento e falsos positivos.
function ravltSheetHtml(sh){
  const T=sh.trials, col=t=>T.find(x=>x.trial===t);
  const head=['Lista A','A1','A2','A3','A4','A5','Lista B','B1','A6','A7','Lista A'];
  const rows=sh.list_a.map((w,i)=>{
    const cell=t=>{const c=col(t).cells[i];return `<td><button type="button" class="rv-cell" data-rv="${esc(c.cell)}" data-trial="${t}" title="${esc(t)} · ${esc(c.word)}"></button><input type="hidden" data-raw="${esc(c.cell)}"></td>`;};
    return `<tr><th>${esc(w)}</th>${['A1','A2','A3','A4','A5'].map(cell).join('')}<th class="rv-b">${esc(sh.list_b[i]||'')}</th>${['B1','A6','A7'].map(cell).join('')}<th>${esc(w)}</th></tr>`;
  }).join('');
  const tot=t=>`<td><b data-rv-total="${t}">0</b></td>`;
  const intr=['A1','A2','A3','A4','A5','B1','A6','A7'].map(t=>
    `<label class="field">${t}<input type="text" data-rv-intr="${t}" placeholder="ex.: gato, casa">`
    +sh.intrusions[t].map(c=>`<input type="hidden" data-raw="${esc(c)}" data-text>`).join('')+`</label>`).join('');
  const rec=sh.recognition.map(r=>`<button type="button" class="rv-rec" data-rv-rec="${esc(r.cell)}"><span class="rv-sn"></span>${esc(r.word)}</button><input type="hidden" data-raw="${esc(r.cell)}" data-text>`).join('');
  return `<section class="ravlt">
    <div class="ravlt-head"><b>Folha de respostas e correção</b><span class="muted small">Toque nas palavras na ordem em que o paciente evocou. Toque de novo para desmarcar.</span></div>
    <div class="table-scroll"><table class="ravlt-grid"><thead><tr>${head.map((h,i)=>`<th class="${i===0||i===6||i===10?'rv-list':''}">${h}</th>`).join('')}</tr></thead>
      <tbody>${rows}</tbody>
      <tfoot><tr><th>TOTAL</th>${['A1','A2','A3','A4','A5'].map(tot).join('')}<th>TOTAL</th>${['B1','A6','A7'].map(tot).join('')}<th></th></tr></tfoot></table></div>
    <h4 class="ravlt-sub">Quadro de intrusões <span class="muted small">(palavras ditas que não estão na lista, separadas por vírgula)</span></h4>
    <div class="ravlt-intr">${intr}</div>
    <h4 class="ravlt-sub">Lista para o reconhecimento <span class="muted small">toque: S (reconheceu) → N (não reconheceu) → vazio</span>
      <button type="button" class="btn ghost xs" id="rvFillN">Marcar N nas que faltam</button></h4>
    <div class="ravlt-rec">${rec}</div>
  </section>`;
}
function rvRenumber(trial){
  // mantém a ordem de evocação contínua (1, 2, 3…) depois de desmarcar
  const btns=[...els.raw.querySelectorAll(`.rv-cell[data-trial="${trial}"]`)].filter(b=>b.textContent!=='');
  btns.sort((a,b)=>Number(a.textContent)-Number(b.textContent)).forEach((b,i)=>{b.textContent=i+1;b.nextElementSibling.value=i+1;});
  const t=els.raw.querySelector(`[data-rv-total="${trial}"]`); if(t) t.textContent=btns.length;
}
els.raw.addEventListener('click',e=>{
  const b=e.target.closest('.rv-cell');
  if(b){
    const trial=b.dataset.trial, inp=b.nextElementSibling;
    if(b.textContent===''){
      const used=[...els.raw.querySelectorAll(`.rv-cell[data-trial="${trial}"]`)].filter(x=>x.textContent!=='').length;
      b.textContent=used+1; inp.value=used+1; b.classList.add('on');
    }else{ b.textContent=''; inp.value=''; b.classList.remove('on'); }
    rvRenumber(trial); return;
  }
  const r=e.target.closest('.rv-rec');
  if(r){
    const inp=r.nextElementSibling, nxt={'':'S','S':'N','N':''}[inp.value||''];
    inp.value=nxt; r.dataset.sn=nxt; r.querySelector('.rv-sn').textContent=nxt; return;
  }
  if(e.target.id==='rvFillN'){
    els.raw.querySelectorAll('.rv-rec').forEach(x=>{const i=x.nextElementSibling; if(!i.value){i.value='N';x.dataset.sn='N';x.querySelector('.rv-sn').textContent='N';}});
  }
});
els.raw.addEventListener('input',e=>{
  const t=e.target; if(!t.dataset || !t.dataset.rvIntr) return;
  const words=t.value.split(',').map(x=>x.trim()).filter(Boolean);
  [...t.parentElement.querySelectorAll('input[type=hidden]')].forEach((h,i)=>{h.value=words[i]||'';});
});

// Botões de toque dos itens: marcam o valor no input (e desmarcam se tocar de novo).
function syncChips(input){
  const seg=input.parentElement.querySelector('.score-seg'); if(!seg) return;
  seg.querySelectorAll('button').forEach(b=>b.classList.toggle('on',input.value!=='' && Number(b.dataset.set)===Number(input.value)));
}
function syncSection(sec){
  const p=sec.querySelector('[data-prog]'); if(!p) return;
  const ins=[...sec.querySelectorAll('[data-raw]')], n=ins.filter(i=>i.value!=='').length;
  p.textContent=`${n}/${ins.length}`; p.classList.toggle('done',n===ins.length);
}
els.raw.addEventListener('click',e=>{
  const b=e.target.closest('[data-set]'); if(!b) return;
  const input=b.closest('.raw-field').querySelector('[data-raw]');
  input.value=input.value!=='' && Number(input.value)===Number(b.dataset.set)?'':b.dataset.set;
  input.dispatchEvent(new Event('input',{bubbles:true}));
});
els.raw.addEventListener('input',e=>{
  const t=e.target; if(!t||!t.dataset||!('raw' in t.dataset)) return;
  syncChips(t); const sec=t.closest('.raw-section'); if(sec) syncSection(sec);
});
els.raw.addEventListener('input',e=>{
  const t=e.target; if(!t||!t.dataset||!('calc' in t.dataset)) return;
  if(t.value==='') delete t.dataset.touched; else t.dataset.touched='1';
});
function collectRaw(){
  const out={};
  document.querySelectorAll('[data-raw]').forEach(i=>{
    if(i.dataset.calc==='1' && i.dataset.touched!=='1') return; // deixa a planilha calcular
    if(i.value==='' && i.dataset.raw.startsWith(VIN_P)) return; // item do Vineland em branco
    out[i.dataset.raw]=i.value===''?'':('text' in i.dataset?i.value:Number(i.value));
  });
  return out;
}
function collectParams(){const out={};document.querySelectorAll('[data-param]').forEach(i=>out[i.dataset.param]=i.value);return out;}
els.clear.addEventListener('click',()=>{
  document.querySelectorAll('[data-raw]').forEach(i=>{i.value='';delete i.dataset.touched;syncChips(i);});
  els.raw.querySelectorAll('.rv-cell').forEach(b=>{b.textContent='';b.classList.remove('on');});
  els.raw.querySelectorAll('[data-rv-total]').forEach(t=>{t.textContent='0';});
  els.raw.querySelectorAll('.rv-rec').forEach(r=>{r.dataset.sn='';r.querySelector('.rv-sn').textContent='';});
  els.raw.querySelectorAll('[data-rv-intr]').forEach(i=>{i.value='';});
  protoSync();
  els.raw.querySelectorAll('.raw-section').forEach(syncSection);
  els.raw.querySelectorAll('[data-vin-crit]').forEach(i=>{i.dataset.zero='';});
  vinSync();
});

// Mostra nos campos calculados o valor que a planilha obteve — sem apagar o que a
// pessoa digitou (campos com data-touched são preservados).
function fillAutoFields(result){
  (result.raw_scores||[]).forEach(f=>{
    if(!f.allow_override_formula)return;
    const sel=(window.CSS&&CSS.escape)?CSS.escape(f.cell):f.cell;
    const el=document.querySelector(`[data-raw="${sel}"][data-calc]`);
    if(el && el.dataset.touched!=='1')
      el.value=(typeof f.value==='number'&&Number.isFinite(f.value))?f.value:'';
  });
}

els.calc.addEventListener('click',async()=>{
  if(!state.meta)return; const p=patient();
  const needsDates=state.meta.input_mode!=='itens';
  if(needsDates && (!p.birth_date||!p.application_date)){toast('Informe nascimento e data de aplicação.',true);return;}
  els.calc.disabled=true;els.calc.textContent='Calculando…';
  try{
    const result=await api('/api/score',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({test:state.meta.name,patient:p,raw_scores:collectRaw(),parameters:collectParams()})});
    state.result=result;
    try{ window.afterLaudo && window.afterLaudo(); }catch{}
    saveTestResult(result,p);
    renderResults(result); fillAutoFields(result); els.testReportBtn.disabled=!state.openaiConfigured; renderArchive(); toast('Resultados recalculados. Clique em "Arquivar teste" para incluí-lo na Avaliação Completa.');
    els.results.scrollIntoView({behavior:'smooth',block:'start'});
  }catch(e){toast(e.message,true);}finally{els.calc.disabled=false;els.calc.textContent='Calcular resultados';}
});

// ---------- Testes arquivados (só eles entram na Avaliação Completa) ----------
// state.results = testes arquivados; state.result = o teste calculado na tela.
function reportIsFor(rep,test){return !!rep.teste && String(rep.teste).toLowerCase().includes(String(test).toLowerCase());}
function renderArchive(){
  const cur=state.result, arch=cur&&state.results.find(x=>x.test===cur.test);
  const btn=$('#archiveBtn');
  if(btn){
    btn.hidden=!cur;
    btn.disabled=!!arch&&arch===cur;
    btn.textContent=!arch?'📁 Arquivar teste':arch===cur?'✓ Arquivado':'📁 Atualizar arquivado';
  }
  $('#archivedList').innerHTML=state.results.length
    ? `<div class="archived-title">Testes arquivados (${state.results.length})</div>`+state.results.map(r=>{
        const done=state.testReports.some(x=>reportIsFor(x,r.test));
        return `<span class="archived-chip">${esc(r.test)}${done?' <small>• laudo pronto</small>':''}<button type="button" data-unarchive="${esc(r.test)}" title="Remover da Avaliação Completa">×</button></span>`;
      }).join('')
    : '<p class="muted small">Nenhum teste arquivado. Calcule um teste e clique em "Arquivar teste".</p>';
  els.integratedBtn.disabled=!state.openaiConfigured||(!state.results.length&&!state.anamnesis);
}
$('#archiveBtn').addEventListener('click',()=>{
  const r=state.result; if(!r)return;
  const ix=state.results.findIndex(x=>x.test===r.test);
  if(ix>=0){
    // valores mudaram: o laudo individual antigo não vale mais
    state.results[ix]=r; state.testReports=state.testReports.filter(x=>!reportIsFor(x,r.test));
    toast(`${r.test}: arquivo atualizado.`);
  }else{ state.results.push(r); toast(`${r.test} arquivado para a Avaliação Completa.`); }
  renderArchive();
});
$('#archivedList').addEventListener('click',e=>{
  const t=e.target.closest('[data-unarchive]')?.dataset.unarchive; if(!t)return;
  state.results=state.results.filter(x=>x.test!==t);
  state.testReports=state.testReports.filter(x=>!reportIsFor(x,t));
  renderArchive(); toast(`${t} removido da Avaliação Completa.`);
});

function visibleTable(table){
  // Mantém fidelidade à planilha, mas remove colunas auxiliares completamente vazias.
  const keep=table.columns.map((_,i)=>table.rows.some(r=>r.values[i]!==''&&r.values[i]!==null));
  return {columns:table.columns.filter((_,i)=>keep[i]),rows:table.rows.map(r=>({...r,values:r.values.filter((_,i)=>keep[i])}))};
}
function renderResults(result){
  els.results.hidden=false; els.tables.innerHTML=result.tables.map((t,ti)=>{
    const v=visibleTable(t); if(!v.columns.length)return'';
    return `<article class="result-table-card"><div class="result-table-title">${esc(t.title||`Tabela ${ti+1}`)}</div><div class="table-scroll"><table class="result-table"><thead><tr>${v.columns.map(c=>`<th>${esc(c.label)}</th>`).join('')}</tr></thead><tbody>${v.rows.map(r=>`<tr>${r.values.map(x=>`<td class="${parseNum(x)!==null?'num':''}">${esc(x??'')}</td>`).join('')}</tr>`).join('')}</tbody></table></div></article>`;
  }).join('');
  renderCharts(result);
}

// ---------- Gráficos SVG sem bibliotecas externas ----------
function seriesFromTable(table, preferred=/ponderad|composto|percentil|escore.?t|padron|quociente/i){
  if(!table)return null; const cols=table.columns; let numIx=cols.findIndex(c=>preferred.test(c.label));
  if(numIx<0){numIx=cols.findIndex((c,i)=>table.rows.filter(r=>parseNum(r.values[i])!==null).length>=3);} if(numIx<0)return null;
  let labelIx=cols.findIndex((c,i)=>i!==numIx && table.rows.filter(r=>typeof r.values[i]==='string'&&r.values[i].trim()).length>=3); if(labelIx<0)labelIx=0;
  const points=table.rows.map(r=>({label:String(r.values[labelIx]??''),value:parseNum(r.values[numIx])})).filter(p=>p.label&&p.value!==null).slice(0,24);
  return points.length>=2?{title:cols[numIx].label,points}:null;
}
// Cor da barra por faixa clínica (ponderados: média 10/dp 3; compostos: média 100/dp 15).
function bandColor(v,vmax){
  const comp=vmax>25, mean=comp?100:10, sd=comp?15:3, z=(v-mean)/sd;
  if(z<=-2)return '#c0392f';       // deficitário
  if(z<=-1)return '#e08128';       // limítrofe
  if(z<0)  return '#d8b530';       // média inferior
  if(z<1)  return '#2e8b57';       // média
  return '#2f6db3';                // média superior +
}
function svgBar(series){
  const W=680,H=300,pad=48,bw=Math.max(12,(W-pad*2)/series.points.length*.62);const vals=series.points.map(p=>p.value);const min=Math.min(0,...vals),max=Math.max(1,...vals);const span=max-min||1;
  const y=v=>H-44-(v-min)/span*(H-85); const base=y(0); const step=(W-pad*2)/series.points.length;
  const bars=series.points.map((p,i)=>{const x=pad+i*step+(step-bw)/2, yy=Math.min(base,y(p.value)),hh=Math.max(2,Math.abs(y(p.value)-base));const col=bandColor(p.value,max);return `<g><rect x="${x}" y="${yy}" width="${bw}" height="${hh}" rx="4" fill="${col}"/><text x="${x+bw/2}" y="${yy-5}" text-anchor="middle" font-size="10" fill="#3d4759">${Math.round(p.value*10)/10}</text><text transform="translate(${x+bw/2},${H-32}) rotate(-35)" text-anchor="end" font-size="9" fill="#727d92">${esc(p.label.slice(0,22))}</text></g>`}).join('');
  const leg=[['#c0392f','Deficitário'],['#e08128','Limítrofe'],['#d8b530','Média inf.'],['#2e8b57','Média'],['#2f6db3','Média sup.+']]
    .map(([c,t],i)=>`<g transform="translate(${pad+i*118},14)"><rect width="10" height="10" rx="2" fill="${c}"/><text x="14" y="9" font-size="9" fill="#5a6479">${t}</text></g>`).join('');
  return `<svg class="chart-svg" viewBox="0 0 ${W} ${H}" role="img">${leg}<line x1="${pad}" x2="${W-pad}" y1="${base}" y2="${base}" stroke="#dde3ef"/>${bars}</svg>`;
}
function svgLine(series){
  const W=680,H=300,p=48,vals=series.points.map(x=>x.value),min=Math.min(0,...vals),max=Math.max(1,...vals),span=max-min||1;const x=i=>p+i*(W-p*2)/Math.max(1,series.points.length-1),y=v=>H-50-(v-min)/span*(H-90);
  const pts=series.points.map((d,i)=>`${x(i)},${y(d.value)}`).join(' ');const dots=series.points.map((d,i)=>`<circle cx="${x(i)}" cy="${y(d.value)}" r="4" fill="#2f57b8"/><text x="${x(i)}" y="${y(d.value)-9}" text-anchor="middle" font-size="10">${Math.round(d.value*10)/10}</text><text x="${x(i)}" y="${H-30}" text-anchor="middle" font-size="9" fill="#727d92">${esc(d.label.slice(0,14))}</text>`).join('');
  return `<svg class="chart-svg" viewBox="0 0 ${W} ${H}"><polyline points="${pts}" fill="none" stroke="#2f57b8" stroke-width="3" stroke-linejoin="round"/>${dots}</svg>`;
}
function svgRadar(series){
  const pts=series.points.slice(0,12),W=560,H=360,cx=W/2,cy=H/2+5,R=125,max=Math.max(100,...pts.map(p=>p.value));const n=pts.length;
  const xy=(i,r)=>{const a=-Math.PI/2+i*2*Math.PI/n;return[cx+Math.cos(a)*r,cy+Math.sin(a)*r]};let grid='';for(let k=1;k<=4;k++){grid+=`<polygon points="${pts.map((_,i)=>xy(i,R*k/4).join(',')).join(' ')}" fill="none" stroke="#e5e9f0"/>`;}
  const poly=pts.map((p,i)=>xy(i,R*Math.max(0,p.value)/max).join(',')).join(' ');const labels=pts.map((p,i)=>{const [x,y]=xy(i,R+24);return `<text x="${x}" y="${y}" text-anchor="middle" font-size="9" fill="#5a6479">${esc(p.label.slice(0,18))}</text>`}).join('');
  return `<svg class="chart-svg" viewBox="0 0 ${W} ${H}">${grid}<polygon points="${poly}" fill="#2f57b829" stroke="#2f57b8" stroke-width="2.5"/>${labels}</svg>`;
}
// ---------- WISC-IV / WAIS: gráficos de índices e de subtestes ----------
// Dois gráficos, montados dinamicamente a partir dos dados corrigidos do paciente:
//  1) "QI e Índices" — barras por índice (ICV/IOP/IMO/IVP/QIT) em pontos compostos,
//     faixa da Média (90–109) ao fundo e sobreposição translúcida do IC 95%.
//  2) "Perfil de Subtestes" — barras horizontais Obtido × Esperado (média = 10).
const WECHSLER_INDEX_ABBR=[
  [/q\.?\s*i\.?\s*total|qi\s*total|escala\s*total/i,'QIT'],
  [/compreens[ãa]o\s+verbal|verbal\s+comprehension/i,'ICV'],
  [/(organiza[çc][ãa]o|racioc[íi]nio)\s+perceptual|perceptual\s+(reasoning|organi)/i,'IOP'],
  [/mem[óo]ria\s+operacional|working\s+memory/i,'IMO'],
  [/velocidade\s+de\s+processamento|processing\s+speed/i,'IVP'],
];
const WECHSLER_INDEX_ORDER=['ICV','IOP','IMO','IVP','QIT'];
const WECHSLER_INDEX_COLORS={ICV:'#4a86c6',IOP:'#e08a3c',IMO:'#9aa0a6',IVP:'#f2c33d',QIT:'#5aa85a'};
const WISC_SUBTEST_ABBR=[
  [/cubos/i,'CB'],[/semelhan/i,'SM'],[/d[íi]gitos/i,'DG'],
  [/conceitos?\s+figurativos?/i,'CN'],[/c[óo]digo/i,'CD'],[/vocabul[áa]rio/i,'VC'],
  [/sequ[êe]ncia\s+de\s+n[úu]meros/i,'SNL'],[/racioc[íi]nio\s+matricial/i,'RM'],
  [/compreens[ãa]o/i,'CO'],[/procurar\s+s[íi]mbolos/i,'PS'],
  [/completar\s+figuras/i,'CF'],[/cancelamento/i,'CA'],
  [/informa[çc][ãa]o/i,'IN'],[/aritm[ée]tica/i,'AR'],
  [/racioc[íi]nio\s+com\s+palavras/i,'RP'],
];
function _abbr(name,table){
  const s=String(name||'');
  for(const [re,ab] of table) if(re.test(s)) return ab;
  return s.replace(/\s*[\(\-–].*$/,'').trim().slice(0,4).toUpperCase();
}
function wechslerIndexSeries(tables){
  const find=(cols,re)=>cols.findIndex(c=>re.test(c.label||''));
  for(const t of tables||[]){
    const cols=t.columns||[];
    const vi=find(cols,/ponto\s*composto|pts?\s*compostos/i);
    const li=find(cols,/escala|[íi]ndice/i);
    if(vi<0||li<0) continue;
    const ci=find(cols,/intervalo\s+de\s+confian/i);
    const pi=find(cols,/percentil/i);
    const by={};
    for(const r of t.rows||[]){
      const value=parseNum(r.values[vi]); if(value===null) continue;
      const full=String(r.values[li]||'').trim(); if(!full) continue;
      const ab=_abbr(full,WECHSLER_INDEX_ABBR);
      if(!WECHSLER_INDEX_ORDER.includes(ab)) continue;
      const m=ci>=0?String(r.values[ci]||'').match(/(-?\d+(?:[.,]\d+)?)\s*[-–a]\s*(-?\d+(?:[.,]\d+)?)/):null;
      by[ab]={label:ab,full,value,
        low:m?parseNum(m[1]):null,high:m?parseNum(m[2]):null,
        pct:pi>=0?parseNum(r.values[pi]):null};
    }
    const points=WECHSLER_INDEX_ORDER.map(k=>by[k]).filter(Boolean);
    if(points.length>=2) return {title:'QI e Índices WISC-IV',points};
  }
  return null;
}
function wechslerSubtestSeries(tables){
  for(const t of tables||[]){
    const cols=t.columns||[];
    const ni=cols.findIndex(c=>/^teste$|subteste/i.test(c.label||''));
    const wi=cols.findIndex(c=>/pontos?\s*ponderad/i.test(c.label||''));
    if(ni<0||wi<0) continue;
    const points=[];
    for(const r of t.rows||[]){
      const w=parseNum(r.values[wi]); if(w===null) continue;
      const name=String(r.values[ni]||'').trim();
      if(!name||/soma|m[ée]dia|convers|escala/i.test(name)) continue;
      points.push({label:_abbr(name,WISC_SUBTEST_ABBR),full:name,obtido:w,esperado:10});
    }
    if(points.length>=3) return {title:'WISC-IV — Perfil de Subtestes',points};
  }
  return null;
}
function svgWechslerIndex(series){
  const pts=series.points;
  const W=1000,H=330,L=50,Rp=16,T=30,Bp=38;
  const lo=0,hi=160,plotW=W-L-Rp,plotH=H-T-Bp;
  const y=v=>T+(hi-Math.max(lo,Math.min(hi,v)))/(hi-lo)*plotH;
  const step=plotW/pts.length, bw=Math.min(76,step*0.5);
  const cx=i=>L+(i+0.5)*step;
  let grid='';
  for(let v=lo;v<=hi;v+=10){
    grid+=`<line x1="${L}" x2="${W-Rp}" y1="${y(v)}" y2="${y(v)}" stroke="#edeff4"/>`
        +`<text x="${L-6}" y="${y(v)+3}" text-anchor="end" font-size="9" fill="#8a94a6">${v}</text>`;
  }
  const band=`<rect x="${L}" y="${y(109)}" width="${plotW}" height="${y(90)-y(109)}" fill="#eeb8db" opacity="0.5"/>`;
  const bars=pts.map((p,i)=>{
    const c=cx(i),x=c-bw/2,top=y(p.value),base=y(lo),col=WECHSLER_INDEX_COLORS[p.label]||'#4a86c6';
    let g=`<rect x="${x}" y="${top}" width="${bw}" height="${base-top}" fill="${col}"/>`;
    if(p.low!=null&&p.high!=null)
      g+=`<rect x="${x}" y="${y(p.high)}" width="${bw}" height="${y(p.low)-y(p.high)}" fill="${col}" opacity="0.4"/>`;
    g+=`<text x="${c}" y="${top-6}" text-anchor="middle" font-size="12" font-weight="700" fill="#1b2333">${esc(p.value)}</text>`;
    g+=`<text x="${c}" y="${H-Bp+15}" text-anchor="middle" font-size="11" font-weight="600" fill="#3d4759">${esc(p.label)}</text>`;
    return `<g>${g}</g>`;
  }).join('');
  return `<svg class="chart-svg chart-svg--wisc" viewBox="0 0 ${W} ${H}" role="img">`
    +`<text x="${W/2}" y="18" text-anchor="middle" font-size="14" font-weight="700" fill="#1b2333">QI e Índices WISC-IV</text>`
    +band+grid
    +`<line x1="${L}" x2="${L}" y1="${T}" y2="${y(lo)}" stroke="#c9cfdb"/><line x1="${L}" x2="${W-Rp}" y1="${y(lo)}" y2="${y(lo)}" stroke="#c9cfdb"/>`
    +bars
    +`<g transform="translate(${W-Rp-150},${T-2})"><rect width="22" height="9" fill="#eeb8db" opacity="0.7"/><text x="28" y="8" font-size="9" fill="#5a6479">Média (90–109)</text></g>`
    +`</svg>`;
}
function svgWechslerSubtests(series){
  const pts=series.points, n=pts.length;
  const W=980,rowH=28,T=48,Bp=30,L=52,Rp=18;
  const H=T+Bp+n*rowH, xlo=0,xhi=19,plotW=W-L-Rp,plotH=n*rowH;
  const x=v=>L+(Math.max(xlo,Math.min(xhi,v))-xlo)/(xhi-xlo)*plotW;
  const barH=9;
  let grid='';
  for(let v=xlo;v<=xhi;v++){
    grid+=`<line x1="${x(v)}" x2="${x(v)}" y1="${T}" y2="${T+plotH}" stroke="${v===10?'#c9433f':'#eceff4'}" stroke-width="${v===10?1.2:1}"/>`;
    if(v===0||v%2===1) grid+=`<text x="${x(v)}" y="${T+plotH+13}" text-anchor="middle" font-size="8.5" fill="#8a94a6">${v}</text>`;
  }
  const rows=pts.map((p,i)=>{
    const cy=T+i*rowH+rowH/2;
    return `<g>`
      +`<rect x="${L}" y="${cy-barH-1}" width="${Math.max(0,x(p.esperado)-L)}" height="${barH}" fill="#e6a8cf"/>`
      +`<rect x="${L}" y="${cy+1}" width="${Math.max(0,x(p.obtido)-L)}" height="${barH}" fill="#3f76c0"/>`
      +`<text x="${L-8}" y="${cy+3}" text-anchor="end" font-size="10" font-weight="700" fill="#3d4759">${esc(p.label)}</text>`
      +`<text x="${x(p.obtido)+4}" y="${cy+barH+1}" font-size="8.5" fill="#5a6479">${esc(p.obtido)}</text>`
      +`</g>`;
  }).join('');
  return `<svg class="chart-svg chart-svg--wisc" viewBox="0 0 ${W} ${H}" role="img">`
    +`<text x="${W/2}" y="18" text-anchor="middle" font-size="14" font-weight="700" fill="#1b2333">WISC-IV — Perfil de Subtestes</text>`
    +`<g transform="translate(${L},26)"><rect width="11" height="9" fill="#3f76c0"/><text x="15" y="8" font-size="9" fill="#5a6479">Obtido</text>`
    +`<rect x="72" width="11" height="9" fill="#e6a8cf"/><text x="87" y="8" font-size="9" fill="#5a6479">Esperado (10)</text></g>`
    +grid+rows+`</svg>`;
}

// ---------- Perfil Sensorial 2 — gráficos de seção e de quadrante ----------
function _psSeries(table){
  if(!table) return null;
  const cols=table.columns.map(c=>String(c.label||'').toLowerCase());
  const li=0, ri=cols.findIndex(c=>/raz|ratio/.test(c));
  const bi=cols.findIndex(c=>/bruta|bruto/.test(c)), mi=cols.findIndex(c=>/m[áa]xim/.test(c));
  const pts=[];
  for(const r of table.rows||[]){
    const label=String(r.values[li]??'').trim(); if(!label) continue;
    let pct=ri>=0?parseNum(r.values[ri]):null;
    if(pct!==null && pct<=1.5) pct*=100;                       // razão 0–1 -> %
    if(pct===null && bi>=0 && mi>=0){
      const b=parseNum(r.values[bi]), mx=parseNum(r.values[mi]);
      if(b!==null && mx) pct=b/mx*100;
    }
    if(pct===null) continue;
    pts.push({label,value:Math.round(pct)});
  }
  return pts.length>=2?{points:pts}:null;
}
function svgPercentBars(series,{horizontal=false}={}){
  const pts=series.points, n=pts.length, C='#e0a52b';
  if(horizontal){
    const W=680,rowH=30,T=20,B=16,L=150,Rp=52,H=T+B+n*rowH,plotW=W-L-Rp;
    const x=v=>L+Math.max(0,Math.min(100,v))/100*plotW;
    let grid='';
    for(let v=0;v<=100;v+=25) grid+=`<line x1="${x(v)}" x2="${x(v)}" y1="${T}" y2="${T+n*rowH}" stroke="#eceff4"/>`
      +`<text x="${x(v)}" y="${T+n*rowH+12}" text-anchor="middle" font-size="8.5" fill="#8a94a6">${v}%</text>`;
    const rows=pts.map((p,i)=>{const cy=T+i*rowH+rowH/2;return `<g>`
      +`<rect x="${L}" y="${cy-8}" width="${Math.max(1,x(p.value)-L)}" height="16" rx="3" fill="${C}"/>`
      +`<text x="${L-8}" y="${cy+4}" text-anchor="end" font-size="10" fill="#3d4759">${esc(p.label.slice(0,24))}</text>`
      +`<text x="${x(p.value)+5}" y="${cy+4}" font-size="10" font-weight="700" fill="#1b2333">${p.value}%</text></g>`;}).join('');
    return `<svg class="chart-svg" viewBox="0 0 ${W} ${H}" role="img">${grid}${rows}</svg>`;
  }
  const W=680,H=300,L=44,Rp=16,T=24,B=54,plotH=H-T-B,step=(W-L-Rp)/n;
  const bw=Math.min(64,step*0.6), y=v=>T+(100-Math.max(0,Math.min(100,v)))/100*plotH;
  let grid='';
  for(let v=0;v<=100;v+=25) grid+=`<line x1="${L}" x2="${W-Rp}" y1="${y(v)}" y2="${y(v)}" stroke="#eceff4"/>`
    +`<text x="${L-6}" y="${y(v)+3}" text-anchor="end" font-size="8.5" fill="#8a94a6">${v}%</text>`;
  const bars=pts.map((p,i)=>{const c=L+(i+0.5)*step;return `<g>`
    +`<rect x="${c-bw/2}" y="${y(p.value)}" width="${bw}" height="${y(0)-y(p.value)}" rx="3" fill="${C}"/>`
    +`<text x="${c}" y="${y(p.value)-5}" text-anchor="middle" font-size="10" font-weight="700" fill="#1b2333">${p.value}%</text>`
    +`<text transform="translate(${c},${H-B+14}) rotate(-20)" text-anchor="end" font-size="9" fill="#727d92">${esc(p.label.slice(0,20))}</text></g>`;}).join('');
  return `<svg class="chart-svg" viewBox="0 0 ${W} ${H}" role="img">${grid}<line x1="${L}" x2="${W-Rp}" y1="${y(0)}" y2="${y(0)}" stroke="#c9cfdb"/>${bars}</svg>`;
}
function sensoryProfileCharts(result){
  const findT=re=>(result.tables||[]).find(t=>re.test(t.title||''));
  const out=[];
  const secS=_psSeries(findT(/se[çc][ãa]o|se[çc][õo]es/i));
  if(secS){
    out.push({title:'Perfil por seção sensorial',svg:svgPercentBars(secS,{horizontal:true})});
    out.push({title:'Perfil por seção — radar',svg:svgRadar({points:secS.points})});
  }
  const quadT=findT(/quadrante/i);
  let quadS=_psSeries(quadT);
  if(quadS){
    quadS={points:quadS.points.filter(p=>!/nenhum/i.test(p.label))};
    if(quadS.points.length>=2){
      out.push({title:'Perfil por quadrante',svg:svgPercentBars(quadS,{})});
      out.push({title:'Perfil por quadrante — radar',svg:svgRadar({points:quadS.points})});
    }
  }
  return out;
}

// Retorna [{title, svg}] com os gráficos de um resultado (reaproveitado no laudo).
function chartsFor(result){
  if(result.chart_type==='escala') return [];
  if(result.chart_type==='learning_curve'){
    const wanted=/^(A[1-7]|B1|T1|T2|T3|Tentativa\s*\d+)/i;
    const pts=(result.raw_scores||[]).map(x=>({label:x.label,value:parseNum(x.value)})).filter(x=>x.value!==null&&wanted.test(x.label)).slice(0,10);
    if(pts.length>=3) return [{title:'Curva de aprendizagem • pontos brutos',svg:svgLine({title:'',points:pts})}];
  }
  if(result.chart_type==='sensory_profile'){
    const s=sensoryProfileCharts(result);
    if(s.length) return s;
  }
  const cand=result.tables.map(t=>seriesFromTable(t)).filter(Boolean);
  if(result.chart_type==='wechsler'){
    const out=[];
    const idx=wechslerIndexSeries(result.tables);
    if(idx) out.push({title:idx.title,svg:svgWechslerIndex(idx)});
    const subs=wechslerSubtestSeries(result.tables);
    if(subs) out.push({title:subs.title,svg:svgWechslerSubtests(subs)});
    if(out.length) return out;
    const comp=cand.find(s=>/composto|qi/i.test(s.title)); if(comp) return [{title:comp.title,svg:svgBar(comp)}];
  }
  if(!cand.length) return [];
  let chosen=cand.slice(0,1);
  return chosen.filter(Boolean).map(s=>({
    title:s.title,
    svg: result.chart_type==='domains'?svgRadar(s):(result.chart_type==='learning_curve'?svgLine(s):svgBar(s)),
  }));
}
function renderCharts(result){
  const cs=chartsFor(result);
  els.charts.innerHTML=cs.map(c=>{
    const wide=/chart-svg--wisc/.test(c.svg)?' chart-card--wide':'';
    return `<article class="chart-card${wide}"><h3>${esc(c.title)}</h3><p>${esc(result.test)} • ${esc(result.chart_type.replace('_',' '))}</p>${c.svg}</article>`;
  }).join('');
}
// SVG -> PNG (data URL) para embutir no .docx
function chartSvgStandalone(svg){
  const m=svg.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);
  const w=m?m[1]:'680', h=m?m[2]:'300';
  const fam=/chart-svg--wisc/.test(svg)?"'Times New Roman',Times,serif":"Inter,'Segoe UI',Arial,sans-serif";
  return {w:+w,h:+h,xml:svg.replace('<svg ',`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" style="font-family:${fam}" `)};
}
function svgToPng(svg){
  return new Promise(res=>{
    const {w,h,xml}=chartSvgStandalone(svg);
    const img=new Image();
    const url=URL.createObjectURL(new Blob([xml],{type:'image/svg+xml'}));
    img.onload=()=>{
      const c=document.createElement('canvas'); c.width=w*2; c.height=h*2;
      const ctx=c.getContext('2d'); ctx.fillStyle='#fff'; ctx.fillRect(0,0,c.width,c.height);
      ctx.drawImage(img,0,0,c.width,c.height); URL.revokeObjectURL(url);
      try{res(c.toDataURL('image/png'));}catch{res(null);}
    };
    img.onerror=()=>{URL.revokeObjectURL(url);res(null);};
    img.src=url;
  });
}
async function collectChartImages(){
  const out=[];
  for(const r of state.results){
    for(const c of chartsFor(r)){
      const png=await svgToPng(c.svg);
      if(png) out.push({test:r.test,title:c.title,image:png});
    }
  }
  return out;
}

// ---------- IA ----------
function dataTableHtml(cols,rows){
  cols=(cols||[]).map(c=>String(c||'').trim()).filter(Boolean);
  rows=(rows||[]).filter(r=>Array.isArray(r));
  if(!cols.length||!rows.length)return'';
  return `<div class="table-scroll"><table class="result-table"><thead><tr>${
    cols.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${
    rows.map(r=>`<tr>${cols.map((_,j)=>{const v=r[j]??'';return `<td class="${parseNum(v)!==null?'num':''}">${esc(v)}</td>`}).join('')}</tr>`).join('')
  }</tbody></table></div>`;
}
function instrumentAnalysisHtml(entries){
  return (entries||[]).map(e=>{
    if(!e||typeof e!=='object')return'';
    const tabs=(e.tabelas||[]).map(t=>`${t.titulo?`<p class="tbl-cap">${esc(t.titulo)}</p>`:''}${dataTableHtml(t.colunas,t.linhas)}`).join('');
    return `<div class="ai-block"><b>${esc(e.instrumento||'')}</b>${e.objetivo?`<p>${esc(e.objetivo)}</p>`:''}${tabs}${e.comentario?`<p>${esc(e.comentario)}</p>`:''}</div>`;
  }).join('');
}
function renderStructured(obj){
  if(!obj)return''; return Object.entries(obj).map(([k,v])=>{
    const title=k.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
    if(k==='analise_instrumentos') return `<div class="ai-block"><h4>${esc(title)}</h4>${instrumentAnalysisHtml(v)}</div>`;
    if(Array.isArray(v)){if(!v.length)return'';if(typeof v[0]==='object')return `<div class="ai-block"><h4>${esc(title)}</h4>${v.map(x=>`<div class="ai-block">${Object.entries(x).map(([a,b])=>`<b>${esc(a.replaceAll('_',' '))}:</b> ${Array.isArray(b)?esc(b.join('; ')):esc(b)}<br>`).join('')}</div>`).join('')}</div>`;return `<div class="ai-block"><h4>${esc(title)}</h4><ul>${v.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`;}
    if(v&&typeof v==='object')return `<div class="ai-block"><h4>${esc(title)}</h4>${renderStructured(v)}</div>`;
    return `<div class="ai-block"><h4>${esc(title)}</h4><p>${esc(v??'')}</p></div>`;
  }).join('');
}
els.testReportBtn.addEventListener('click',async()=>{
  if(!state.result)return; els.testReportBtn.disabled=true;els.testReportBtn.textContent='Gerando…';
  try{const rep=await api('/api/ai/test-report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({patient:patient(),score_result:state.result,history:state.anamnesis})});state.testReports=state.testReports.filter(x=>x.teste!==rep.teste);state.testReports.push(rep);els.testReportOutput.innerHTML=renderStructured(rep);renderArchive();toast('Laudo do teste gerado.');}catch(e){toast(e.message,true);}finally{els.testReportBtn.disabled=false;els.testReportBtn.textContent='Gerar laudo deste teste';}
});
// Modelo de História de Vida da profissional: História da Doença Atual + 6 tópicos.
const HV_MODEL=[['historia_doenca_atual','HISTÓRIA DE DOENÇA ATUAL'],['periodo_gestacional','Período Gestacional'],
  ['desenvolvimento_global','Desenvolvimento Global'],['alimentacao_sono','Alimentação e Sono'],
  ['historico_familiar_social','Histórico Familiar e Social'],['autonomia_comportamento','Autonomia e Comportamento'],
  ['historico_escolar','Histórico Escolar']];
function hvModelHtml(m){
  const [first,...rest]=HV_MODEL;
  return `<h3>${first[1]}:</h3><p>${esc(m[first[0]]||'')}</p><h3>HISTÓRIA DE VIDA:</h3>`+
    rest.map(([k,t])=>`<p><b>• ${t}:</b><br>${esc(m[k]||'')}</p>`).join('');
}
function hvModelText(m){
  const [first,...rest]=HV_MODEL;
  return `${first[1]}:\n${m[first[0]]||''}\n\nHISTÓRIA DE VIDA:\n\n`+rest.map(([k,t])=>`- ${t}:\n${m[k]||''}`).join('\n\n');
}
function hvHtml(rep){
  if(!rep) return '';
  const {transcricao,identificacao,historia_modelo,...rest}=rep;
  let h='';
  if(historia_modelo){
    h+=`<div class="hv-model"><div class="hv-model-bar"><span class="badge ai">Modelo de História de Vida</span><button type="button" class="btn ghost xs" data-hv-copy>Copiar texto</button></div><div class="hv-model-doc">${hvModelHtml(historia_modelo)}</div></div>`;
    h+=`<details class="ai-block hv-more"><summary><h4>Detalhes da organização (resumo, linha do tempo, lacunas)</h4></summary>${renderStructured(rest)}</details>`;
  } else h+=renderStructured(rest);
  if(Array.isArray(transcricao)&&transcricao.length) h+=`<details class="ai-block hv-ocr"><summary><h4>Transcrição (OCR) — ${transcricao.length} página(s)</h4></summary>${transcricao.map(t=>`<div class="hv-page"><b>${esc(t.documento||'')}${t.pagina?' · pág. '+esc(t.pagina):''}</b><pre>${esc(t.texto||'')}</pre></div>`).join('')}</details>`;
  return h;
}
// Resultado da História de Vida (upload/OCR ou formulário) → tela, estado e aviso de Testes realizados.
function applyAnamnesis(res){
  const {_registro:reg,...rep}=res;
  state.anamnesis=rep;try{ window.afterLaudo && window.afterLaudo(); }catch{}
  els.anamnesisOutput.innerHTML=hvHtml(rep);els.integratedBtn.disabled=false;
  let msg='História de vida organizada com sucesso.';
  if(reg&&reg.id){const p=reg.patient||{};if(!$('#patientName').value.trim()&&p.name)$('#patientName').value=p.name;if(!$('#birthDate').value&&p.birth_date){$('#birthDate').value=p.birth_date;updateAge();}syncHv();msg+=` Salva em Testes realizados (${p.name||'sem nome'}).`;}
  else if(reg&&reg.erro) toast('História organizada, mas não foi salva em Testes realizados: '+reg.erro,true);
  anamnesisAlert(msg,'done');toast('História de vida organizada.');
  els.anamnesisOutput.scrollIntoView({behavior:'smooth',block:'start'});
}
document.addEventListener('click',async e=>{
  if(!e.target.closest('[data-hv-copy]')) return;
  const m=state.anamnesis&&state.anamnesis.historia_modelo; if(!m) return;
  const html=`<div style="font-family:'Times New Roman';font-size:12pt;text-align:justify">${hvModelHtml(m)}</div>`, txt=hvModelText(m);
  try{ await navigator.clipboard.write([new ClipboardItem({'text/html':new Blob([html],{type:'text/html'}),'text/plain':new Blob([txt],{type:'text/plain'})})]); }
  catch{ try{ await navigator.clipboard.writeText(txt); }catch{ toast('Não foi possível copiar.',true); return; } }
  toast('História de vida copiada — cole no Word.');
});
function anamnesisAlert(msg,kind='info'){
  els.anamnesisAlert.textContent=msg; els.anamnesisAlert.hidden=false;
  els.anamnesisAlert.className='alert '+(kind==='error'?'error':'success')+(kind==='done'?' done':'');
}
els.files.addEventListener('change',()=>{
  const fs=[...els.files.files];
  els.fileList.innerHTML=fs.map(f=>`<div>• ${esc(f.name)} (${(f.size/1024/1024).toFixed(1)} MB)</div>`).join('');
  els.analyzeBtn.disabled=!fs.length||!state.openaiConfigured;
  if(fs.length) anamnesisAlert(`${fs.length} arquivo(s) de anamnese carregado(s). Clique em "Analisar e gerar história".`);
  else els.anamnesisAlert.hidden=true;
});
els.analyzeBtn.addEventListener('click',async()=>{
  const fs=[...els.files.files];if(!fs.length)return;els.analyzeBtn.disabled=true;els.analyzeBtn.textContent='Lendo documentos (OCR)… pode levar 1–3 min';
  try{const fd=new FormData();fd.append('patient_json',JSON.stringify(patient()));const pid=currentPatientId();if(pid)fd.append('patient_id',pid);fs.forEach(f=>fd.append('files',f));applyAnamnesis(await api('/api/ai/anamnesis',{method:'POST',body:fd}));}catch(e){anamnesisAlert('Falha ao analisar a anamnese. Verifique os arquivos e tente novamente.','error');toast(e.message,true);}finally{els.analyzeBtn.disabled=false;els.analyzeBtn.textContent='Analisar e gerar história';}
});
// ---------- Modelo de formatação do laudo ----------
function modelAlert(msg,kind='info'){
  els.modelAlert.textContent=msg; els.modelAlert.hidden=false;
  els.modelAlert.className='alert '+(kind==='error'?'error':'success')+(kind==='done'?' done':'');
}
els.modelFiles.addEventListener('change',()=>{
  const fs=[...els.modelFiles.files];
  els.modelFileList.innerHTML=fs.map(f=>`<div>• ${esc(f.name)} (${(f.size/1024/1024).toFixed(1)} MB)</div>`).join('');
  els.analyzeModelBtn.disabled=!fs.length||!state.openaiConfigured;
  if(fs.length) modelAlert(`${fs.length} modelo(s) carregado(s). Clique em "Ler modelo".`);
  else els.modelAlert.hidden=true;
});
els.analyzeModelBtn.addEventListener('click',async()=>{
  const fs=[...els.modelFiles.files];if(!fs.length)return;
  els.analyzeModelBtn.disabled=true;els.analyzeModelBtn.textContent='Lendo modelo…';
  try{
    const fd=new FormData();fs.forEach(f=>fd.append('files',f));
    const rep=await api('/api/ai/laudo-model',{method:'POST',body:fd});
    state.laudoModel=rep;els.modelOutput.innerHTML=renderStructured(rep);
    modelAlert('Modelo carregado — o laudo integrado seguirá esta formatação.','done');
    toast('Modelo de formatação pronto.');
  }catch(e){modelAlert('Falha ao ler o modelo. Verifique o arquivo e tente novamente.','error');toast(e.message,true);}
  finally{els.analyzeModelBtn.disabled=false;els.analyzeModelBtn.textContent='Ler modelo';}
});

// Gera o laudo individual de um teste calculado (usado no fluxo da Avaliação Completa).
async function ensureTestReport(result){
  if(state.testReports.some(r=>r.teste && String(r.teste).toLowerCase().includes(String(result.test).toLowerCase())))return;
  const rep=await api('/api/ai/test-report',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({patient:patient(),score_result:result,history:state.anamnesis})});
  state.testReports=state.testReports.filter(x=>x.teste!==rep.teste);
  state.testReports.push(rep);
}
els.integratedBtn.addEventListener('click',async()=>{
  if(!state.results.length&&!state.anamnesis){toast('Arquive pelo menos um teste ou analise a anamnese.',true);return;}
  els.integratedBtn.disabled=true; const orig='Gerar Avaliação Completa';
  try{
    // 1) laudo de cada teste arquivado que ainda não tem
    const pend=state.results.filter(r=>!state.testReports.some(x=>reportIsFor(x,r.test)));
    for(let i=0;i<pend.length;i++){
      els.integratedBtn.textContent=`Laudo ${i+1}/${pend.length}: ${pend[i].test}…`;
      await ensureTestReport(pend[i]);
    }
    // 2) laudo geral só com os testes arquivados
    els.integratedBtn.textContent='Integrando tudo…';
    const rep=await api('/api/ai/integrated-report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({patient:patient(),anamnesis:state.anamnesis,test_reports:state.testReports.filter(x=>state.results.some(r=>reportIsFor(x,r.test))),raw_results:state.results,external_results:collectExternal(),model:state.laudoModel})});
    state.integrated=rep;renderArchive();els.integratedOutput.innerHTML=renderStructured(rep);
    els.laudoActions.hidden=false;els.docxBtn.hidden=false;
    toast('Avaliação Neuropsicológica Completa gerada.');
    try{ window.afterLaudo && window.afterLaudo(); }catch{}
    els.laudoActions.scrollIntoView({behavior:'smooth',block:'center'});
  }catch(e){
    toast(e.message,true);
    if(/cr[eé]dito/i.test(e.message||'') && window.showView) window.showView('planos');
  }finally{els.integratedBtn.textContent=orig;renderArchive();}
});

// ---------- Salvar laudo integrado em .docx (Word) ----------
async function saveIntegratedDocx(btn){
  if(!state.integrated){toast('Gere a Avaliação Completa primeiro.',true);return;}
  const label=btn?btn.textContent:''; if(btn){btn.disabled=true;btn.textContent='Gerando .docx…';}
  try{
    const charts=await collectChartImages();
    const h={'Content-Type':'application/json'}; if(state.token) h['Authorization']=`Bearer ${state.token}`;
    const r=await fetch('/api/laudo/integrated-docx',{method:'POST',headers:h,
      body:JSON.stringify({patient:patient(),report:state.integrated,tests:state.results.map(x=>x.test),charts})});
    if(!r.ok){let d;try{d=await r.json();}catch{d={detail:await r.text()};}throw new Error(d.detail||`HTTP ${r.status}`);}
    const blob=await r.blob();
    const cd=r.headers.get('Content-Disposition')||'';
    const m=cd.match(/filename="?([^"]+)"?/);
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);
    a.download=m?m[1]:`avaliacao_neuropsicologica_completa_${slugify(patient().name)}_${new Date().toISOString().slice(0,10)}.docx`;
    a.click();URL.revokeObjectURL(a.href);toast('Avaliação Completa salva em .docx.');
  }catch(e){toast(e.message,true);}finally{if(btn){btn.disabled=false;btn.textContent=label;}}
}
els.docxBtn.addEventListener('click',()=>saveIntegratedDocx(els.docxBtn));
els.docxBtn2.addEventListener('click',()=>saveIntegratedDocx(els.docxBtn2));

// ---------- Salvar / imprimir laudo pronto ----------
function laudoHtml(){
  const p=patient(), rep=state.integrated;
  const title=`Avaliação Neuropsicológica Completa — ${p.name||'Paciente'}`;
  const tests=state.results.map(r=>r.test).join(', ')||'—';
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>${esc(title)}</title>
<style>
body{font-family:"Times New Roman",Times,serif;font-size:12pt;max-width:760px;margin:40px auto;padding:0 24px;color:#1a1a1a;line-height:1.6;text-align:justify}
h1{font-size:16pt;border-bottom:2px solid #333;padding-bottom:8px;margin:0 0 16px;text-align:center}
h4{font-size:12pt;text-transform:uppercase;letter-spacing:.04em;color:#333;margin:20px 0 4px;text-align:left}
.meta{font-size:11pt;color:#333;background:#f6f6f6;border:1px solid #e0e0e0;border-radius:8px;padding:12px 14px;margin-bottom:22px;text-align:left}
.ai-block{margin:0 0 4px}p{margin:4px 0}ul{margin:4px 0 4px 18px}
li{text-align:justify}
table{border-collapse:collapse;width:100%;margin:6px 0 14px;font-size:11px}
th,td{border:1px solid #bbb;padding:5px 7px;text-align:left;vertical-align:top}
th{background:#eef2f9;font-weight:700}
.tbl-cap{font-size:11px;font-weight:700;color:#333;margin:10px 0 2px}
.table-scroll{overflow-x:auto}
.chartblock{margin:12px 0;break-inside:avoid}.chartblock svg{max-width:100%;height:auto;border:1px solid #e0e0e0;border-radius:6px;padding:6px;margin:4px 0 12px}
.foot{margin-top:44px;font-size:11px;color:#666;border-top:1px solid #ccc;padding-top:12px}
.sign{margin-top:52px;font-size:13px}.sign-line{margin-top:40px;border-top:1px solid #333;width:280px;padding-top:4px}
@media print{body{margin:0;max-width:none}}
h1{text-align:center;letter-spacing:.02em}
</style></head><body>
<h1>AVALIAÇÃO NEUROPSICOLÓGICA COMPLETA</h1>
<div class="meta">
<b>Nome:</b> ${esc(p.name||'—')}<br>
<b>Data de nascimento:</b> ${esc(p.birth_date||'—')} &nbsp;&nbsp; <b>Data de aplicação:</b> ${esc(p.application_date||'—')}<br>
<b>Sexo:</b> ${esc(p.sex||'—')} &nbsp;&nbsp; <b>Escolaridade:</b> ${esc(p.education||'—')}<br>
<b>Instrumentos aplicados:</b> ${esc(tests)}<br>
<b>Data de emissão:</b> ${new Date().toLocaleDateString('pt-BR')}
</div>
${renderStructured(rep)}
${(()=>{const secs=state.results.map(r=>{const cs=chartsFor(r);if(!cs.length)return'';return `<div class="chartblock"><b>${esc(r.test)}</b>${cs.map(c=>`<div class="tbl-cap">${esc(c.title)}</div>${c.svg}`).join('')}</div>`;}).filter(Boolean).join('');return secs?`<h4>Gráficos por teste</h4>${secs}`:'';})()}
<div class="sign"><div class="sign-line">Profissional responsável — assinatura e registro</div></div>
<div class="foot">Documento gerado pelo NeuroScore com apoio de inteligência artificial. O conteúdo exige revisão, validação clínica e assinatura de profissional habilitado antes de qualquer uso.</div>
</body></html>`;
}
function slugify(s){return (s||'paciente').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^a-z0-9]+/g,'_').replace(/^_+|_+$/g,'')||'paciente';}
els.saveLaudoBtn.addEventListener('click',()=>{
  if(!state.integrated){toast('Gere a Avaliação Completa primeiro.',true);return;}
  const blob=new Blob([laudoHtml()],{type:'text/html;charset=utf-8'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download=`avaliacao_neuropsicologica_completa_${slugify(patient().name)}_${new Date().toISOString().slice(0,10)}.html`;
  a.click();URL.revokeObjectURL(a.href);toast('Avaliação Completa salva.');
});
els.printLaudoBtn.addEventListener('click',()=>{
  if(!state.integrated){toast('Gere a Avaliação Completa primeiro.',true);return;}
  const w=window.open('','_blank');
  if(!w){toast('Permita pop-ups para imprimir.',true);return;}
  w.document.write(laudoHtml());w.document.close();w.focus();
  w.onload=()=>{w.print();};setTimeout(()=>{try{w.print();}catch{}},400);
});

$('#printBtn').addEventListener('click',()=>window.print());
$('#exportBtn').addEventListener('click',()=>{
  const blob=new Blob([JSON.stringify({patient:patient(),results:state.results,anamnesis:state.anamnesis,test_reports:state.testReports,laudo_model:state.laudoModel,integrated_report:state.integrated},null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`neuro_avaliacao_${slugify(patient().name)}_${new Date().toISOString().slice(0,10)}.json`;a.click();URL.revokeObjectURL(a.href);
});

// ---------- Testes realizados (salvos por paciente; CRUD na aba própria) ----------
// Cada cálculo bem-sucedido grava entradas + resultado. Mesmo paciente + teste = atualiza.
async function saveTestResult(result,p){
  if(!state.authEnabled) return;
  const {credits_balance,...clean}=result;
  try{
    await api('/api/test-results',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      patient:p,patient_id:currentPatientId(),test:clean.test||state.meta?.name,
      inputs:{raw_scores:collectRaw(),parameters:collectParams()},result:clean})});
    const note=$('#savedNote'); if(note){note.hidden=false;note.textContent=`✓ Salvo em Testes realizados (${p.name||'sem nome'})`;}
  }catch(e){ toast('Resultado calculado, mas não foi salvo em Testes realizados: '+e.message,true); }
}
function setPatientFields(p){
  $('#patientName').value=p.name||''; $('#birthDate').value=p.birth_date||'';
  $('#applicationDate').value=p.application_date||''; $('#sex').value=p.sex||'';
  $('#education').value=p.education||''; updateAge(); syncHv();
}
// Reabre um teste salvo no corretor, com as entradas preenchidas, para editar e recalcular.
async function openSavedTest(rec){
  setPatientFields(rec.patient||{});
  await selectTest(rec.test);
  const raw=(rec.inputs||{}).raw_scores||{};
  els.raw.querySelectorAll('[data-raw]').forEach(i=>{
    const v=raw[i.dataset.raw]; if(v===undefined||v===null||v==='') return;
    i.value=v; if('calc' in i.dataset) i.dataset.touched='1'; syncChips(i);
  });
  // ficha do RAVLT: reconstrói os toques, o reconhecimento e as intrusões
  els.raw.querySelectorAll('.rv-cell').forEach(b=>{const v=b.nextElementSibling.value; if(v){b.textContent=v;b.classList.add('on');}});
  ['A1','A2','A3','A4','A5','B1','A6','A7'].forEach(t=>{const tt=els.raw.querySelector(`[data-rv-total="${t}"]`); if(tt) tt.textContent=els.raw.querySelectorAll(`.rv-cell.on[data-trial="${t}"]`).length;});
  els.raw.querySelectorAll('.rv-rec').forEach(r=>{const v=r.nextElementSibling.value; r.dataset.sn=v; r.querySelector('.rv-sn').textContent=v;});
  els.raw.querySelectorAll('[data-rv-intr]').forEach(f=>{f.value=[...f.parentElement.querySelectorAll('input[type=hidden]')].map(h=>h.value).filter(Boolean).join(', ');});
  const params=(rec.inputs||{}).parameters||{};
  els.params.querySelectorAll('[data-param]').forEach(i=>{ if(params[i.dataset.param]!==undefined) i.value=params[i.dataset.param]; });
  els.raw.querySelectorAll('.raw-section').forEach(syncSection);
  protoSync(); vinSync();
  if(rec.result && rec.result.tables){ state.result=rec.result; renderResults(rec.result); fillAutoFields(rec.result); els.testReportBtn.disabled=!state.openaiConfigured; renderArchive(); }
}
// Reabre uma História de Vida salva (leitura da anamnese) na aba História de Vida.
function openSavedHistoria(rec){
  setPatientFields(rec.patient||{});
  state.anamnesis=rec.result||null;
  els.anamnesisOutput.innerHTML=hvHtml(state.anamnesis);
  const form=(rec.inputs||{}).formulario; if(form&&window.NS.anamForm) window.NS.anamForm.load(form,rec.patient_id);
  anamnesisAlert(`História de vida salva de ${rec.patient?.name||'paciente sem nome'} — entra no laudo completo.`,'done');
  els.integratedBtn.disabled=!state.openaiConfigured;
}
// Monta a Avaliação Completa com os testes escolhidos e gera o laudo integrado.
function laudoFromSaved(recs){
  if(!recs.length) return;
  setPatientFields(recs[0].patient||{});
  const hv=recs.find(r=>r.test==='História de Vida');
  if(hv){state.anamnesis=hv.result||null;els.anamnesisOutput.innerHTML=hvHtml(state.anamnesis);}
  state.results=recs.filter(r=>r.test!=='História de Vida').map(r=>r.result).filter(r=>r&&r.tables);
  state.testReports=[]; state.integrated=null; state.evalId=null;
  renderArchive();
  els.integratedBtn.scrollIntoView({behavior:'smooth',block:'center'});
  els.integratedBtn.click();
}
window.NS=window.NS||{};
Object.assign(window.NS,{openSavedTest,openSavedHistoria,laudoFromSaved,applyAnamnesis,setPatientFields,anamnesisAlert});

// ---------- Avaliações salvas (nuvem, por profissional) ----------
function currentPatientId(){
  const nm=$('#patientName').value.trim().toLowerCase();
  const p=(state.patients||[]).find(x=>(x.name||'').trim().toLowerCase()===nm);
  return p?p.id:null;
}
function evalPayload(){
  return {patient:patient(),patient_id:currentPatientId(),results:state.results,anamnesis:state.anamnesis,
          test_reports:state.testReports,integrated_report:state.integrated,laudo_model:state.laudoModel,
          external_results:collectExternal()};
}
$('#saveEvalBtn')?.addEventListener('click',async()=>{
  const btn=$('#saveEvalBtn'); btn.disabled=true; const t=btn.textContent; btn.textContent='Salvando…';
  try{
    const method=state.evalId?'PUT':'POST';
    const url=state.evalId?`/api/evaluations/${state.evalId}`:'/api/evaluations';
    const row=await api(url,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(evalPayload())});
    state.evalId=row.id||state.evalId;
    toast('Avaliação salva na sua conta.');
  }catch(e){toast(e.message,true);}finally{btn.disabled=false;btn.textContent=t;}
});
$('#myEvalsBtn')?.addEventListener('click',async()=>{
  const modal=$('#evalsModal'), list=$('#evalsList');
  list.innerHTML='<p class="muted small">Carregando…</p>'; modal.hidden=false;
  try{
    const {evaluations}=await api('/api/evaluations');
    if(!evaluations.length){ list.innerHTML='<p class="muted small">Nenhuma avaliação salva ainda.</p>'; return; }
    list.innerHTML=evaluations.map(ev=>{
      const nm=esc(ev.patient?.name||'(sem nome)');
      const when=new Date(ev.updated_at||ev.created_at).toLocaleString('pt-BR');
      const tests=(ev.tests||[]).map(t=>t.test).filter(Boolean).join(', ');
      return `<div class="eval-row"><div><div class="who">${nm}</div>
        <div class="meta">${esc(tests||'sem testes')} • ${when}</div></div>
        <div class="acts"><button type="button" class="btn ghost" data-open="${ev.id}">Abrir</button>
        <button type="button" class="btn ghost" data-del="${ev.id}">Excluir</button></div></div>`;
    }).join('');
  }catch(e){ list.innerHTML=`<p class="msg err" style="display:block">${esc(e.message)}</p>`; }
});
$('#evalsClose')?.addEventListener('click',()=>$('#evalsModal').hidden=true);
$('#evalsModal')?.addEventListener('click',(e)=>{ if(e.target.id==='evalsModal')$('#evalsModal').hidden=true; });
$('#evalsList')?.addEventListener('click',async(e)=>{
  const open=e.target.dataset.open, del=e.target.dataset.del;
  if(del){
    if(!confirm('Excluir esta avaliação?'))return;
    try{ await api(`/api/evaluations/${del}`,{method:'DELETE'}); $('#myEvalsBtn').click(); toast('Avaliação excluída.'); }
    catch(err){ toast(err.message,true); }
    return;
  }
  if(!open)return;
  try{
    const ev=await api(`/api/evaluations/${open}`);
    loadEvaluation(ev); $('#evalsModal').hidden=true; toast('Avaliação carregada.');
  }catch(err){ toast(err.message,true); }
});
function loadEvaluation(ev){
  const p=ev.patient||{};
  $('#patientName').value=p.name||''; $('#birthDate').value=p.birth_date||'';
  $('#applicationDate').value=p.application_date||''; $('#sex').value=p.sex||'';
  $('#education').value=p.education||''; updateAge();
  state.results=ev.tests||[]; state.anamnesis=ev.anamnesis||null;
  state.testReports=ev.test_reports||[]; state.integrated=ev.integrated_report||null;
  state.laudoModel=ev.laudo_model||null; state.evalId=ev.id;
  state.externalTests=Array.isArray(ev.external_results)?ev.external_results.map(x=>({...x})):[];
  renderExternal();
  if(state.anamnesis){ els.anamnesisOutput.innerHTML=hvHtml(state.anamnesis); }
  if(state.laudoModel){ els.modelOutput.innerHTML=renderStructured(state.laudoModel); }
  if(state.integrated){
    els.integratedOutput.innerHTML=renderStructured(state.integrated);
    els.laudoActions.hidden=false; els.docxBtn.hidden=false;
  }
  if(state.results.length){
    state.result=state.results[state.results.length-1];
    renderResults(state.result); fillAutoFields(state.result);
    els.testReportBtn.disabled=!state.openaiConfigured;
  }
  renderArchive();
}

init();
