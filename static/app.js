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
};

const els = {
  list: $('#testList'), search: $('#testSearch'), title: $('#pageTitle'), raw: $('#rawFields'),
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
};

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

async function api(url, options={}){
  const opt={...options, headers:{...(options.headers||{})}};
  if(state.token) opt.headers['Authorization']=`Bearer ${state.token}`;
  const r=await fetch(url,opt); let data; try{data=await r.json();}catch{data={detail:await r.text()};}
  if(r.status===401 && state.authEnabled){ location.replace('/login.html'); throw new Error('Sessão expirada.'); }
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
    const data=await api('/api/tests'); state.tests=data.tests; renderTestList();
  }catch(e){$('#apiDot').className='status-dot bad';$('#apiStatus').textContent='Servidor indisponível';toast(e.message,true);}
}
function renderTestList(){
  const q=els.search.value.trim().toLowerCase();
  els.list.innerHTML=state.tests.filter(t=>t.name.toLowerCase().includes(q)).map(t=>`<button class="test-item ${state.meta?.name===t.name?'active':''}" data-test="${esc(t.name)}"><span>${esc(t.name)}</span><small>${esc(t.chart_type||'')}</small></button>`).join('');
  els.list.querySelectorAll('.test-item').forEach(b=>b.addEventListener('click',()=>selectTest(b.dataset.test)));
}
els.search.addEventListener('input',renderTestList);
$('#menuBtn').addEventListener('click',()=>$('#sidebar').classList.toggle('open'));

async function selectTest(name){
  els.title.textContent=name; els.raw.innerHTML=''; $('#testLoading').hidden=false; $('#testLoading').textContent='Preparando campos e fórmulas…'; els.calc.disabled=true;
  try{
    state.meta=await api(`/api/tests/${encodeURIComponent(name)}`); state.result=null; renderTestList(); renderInputs();
    $('#sidebar').classList.remove('open');
  }catch(e){$('#testLoading').textContent='Não foi possível preparar este teste.';toast(e.message,true);}
}
function groupFields(fields){
  const groups=[]; let current=[]; let prev=null;
  for(const f of fields){const m=f.cell.match(/\d+$/);const row=m?Number(m[0]):0;if(prev!==null && row-prev>8 && current.length){groups.push(current);current=[];}current.push(f);prev=row;}
  if(current.length)groups.push(current);return groups;
}
function renderInputs(){
  const m=state.meta; $('#testLoading').hidden=true; els.count.textContent=`${m.raw_fields.length} campos`;
  const hidden=(m.detail_fields||[]).length; els.inputMode.textContent=m.input_mode==='pontos_brutos'?'Somente PB':'Entrada original';
  els.inputMode.title=hidden?`${hidden} campos de itens/origem mantidos fora da entrada compacta`:'';
  const groups=groupFields(m.raw_fields);
  els.raw.innerHTML=groups.map((g,i)=>{
    const auto=g.every(f=>f.allow_override_formula);
    const title=auto
      ? 'Automático — a planilha recalcula pelos pontos brutos (idade/sexo conforme a norma do teste)'
      : (groups.length>1?`Bloco ${i+1}`:'Entrada rápida');
    const cells=g.map(f=>{
      const a=!!f.allow_override_formula;
      return `<div class="raw-field${a?' raw-field--auto':''}">`
        +`<label>${esc(f.label)} <span class="cell-ref">${esc(f.cell)}</span></label>`
        +`<input data-raw="${esc(f.cell)}"${a?' data-auto="1" readonly':''} inputmode="decimal" type="number" step="any"`
        +` value="${!a&&typeof f.current==='number'?f.current:''}" placeholder="${a?'auto':'PB'}"`
        +`${a?' title="Preenchido automaticamente ao calcular, a partir do Bloco 1 e da norma do teste."':''} /></div>`;
    }).join('');
    return `<section class="raw-section${auto?' raw-section--auto':''}"><div class="raw-section-title">${title}</div><div class="raw-grid">${cells}</div></section>`;
  }).join('');
  const params=m.parameters||[]; els.paramsPanel.hidden=!params.length;
  els.params.innerHTML=params.map(p=>`<label class="field">${esc(p.label)}<input data-param="${esc(p.cell)}" value="${esc(p.current??'')}" /></label>`).join('');
  els.calc.disabled=!m.raw_fields.length; els.results.hidden=true; els.testReportBtn.disabled=true;
}
// Campos [data-auto] (somas/índices com fórmula) nunca são enviados: a planilha
// os recalcula sozinha pela idade e pelo sexo. Só vão pontos brutos digitados.
function collectRaw(){const out={};document.querySelectorAll('[data-raw]:not([data-auto])').forEach(i=>{out[i.dataset.raw]=i.value===''?'':Number(i.value);});return out;}
function collectParams(){const out={};document.querySelectorAll('[data-param]').forEach(i=>out[i.dataset.param]=i.value);return out;}
els.clear.addEventListener('click',()=>document.querySelectorAll('[data-raw]').forEach(i=>i.value=''));

// Mostra nos campos automáticos (somas dos ponderados / índices) o valor que a
// planilha calculou pela idade e pelo sexo. São só exibição — nunca reenviados.
function fillAutoFields(result){
  (result.raw_scores||[]).forEach(f=>{
    if(!f.allow_override_formula)return;
    const sel=(window.CSS&&CSS.escape)?CSS.escape(f.cell):f.cell;
    const el=document.querySelector(`[data-raw="${sel}"][data-auto]`);
    if(el)el.value=(typeof f.value==='number'&&Number.isFinite(f.value))?f.value:'';
  });
}

els.calc.addEventListener('click',async()=>{
  if(!state.meta)return; const p=patient(); if(!p.birth_date||!p.application_date){toast('Informe nascimento e data de aplicação.',true);return;}
  els.calc.disabled=true;els.calc.textContent='Calculando…';
  try{
    const result=await api('/api/score',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({test:state.meta.name,patient:p,raw_scores:collectRaw(),parameters:collectParams()})});
    state.result=result; const ix=state.results.findIndex(x=>x.test===result.test); if(ix>=0)state.results[ix]=result;else state.results.push(result);
    renderResults(result); fillAutoFields(result); els.testReportBtn.disabled=!state.openaiConfigured; els.integratedBtn.disabled=!state.openaiConfigured; toast('Resultados recalculados.');
    els.results.scrollIntoView({behavior:'smooth',block:'start'});
  }catch(e){toast(e.message,true);}finally{els.calc.disabled=false;els.calc.textContent='Calcular resultados';}
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
function svgBar(series){
  const W=680,H=300,pad=48,bw=Math.max(12,(W-pad*2)/series.points.length*.62);const vals=series.points.map(p=>p.value);const min=Math.min(0,...vals),max=Math.max(1,...vals);const span=max-min||1;
  const y=v=>H-44-(v-min)/span*(H-85); const base=y(0); const step=(W-pad*2)/series.points.length;
  const bars=series.points.map((p,i)=>{const x=pad+i*step+(step-bw)/2, yy=Math.min(base,y(p.value)),hh=Math.max(2,Math.abs(y(p.value)-base));return `<g><rect x="${x}" y="${yy}" width="${bw}" height="${hh}" rx="4" fill="#2f57b8" opacity=".9"/><text x="${x+bw/2}" y="${yy-5}" text-anchor="middle" font-size="10" fill="#3d4759">${Math.round(p.value*10)/10}</text><text transform="translate(${x+bw/2},${H-32}) rotate(-35)" text-anchor="end" font-size="9" fill="#727d92">${esc(p.label.slice(0,22))}</text></g>`}).join('');
  return `<svg class="chart-svg" viewBox="0 0 ${W} ${H}" role="img"><line x1="${pad}" x2="${W-pad}" y1="${base}" y2="${base}" stroke="#dde3ef"/>${bars}</svg>`;
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
function renderCharts(result){
  if(result.chart_type==='learning_curve'){
    const wanted=/^(A[1-7]|B1|T1|T2|T3|Tentativa\s*\d+)/i;
    const pts=(result.raw_scores||[]).map(x=>({label:x.label,value:parseNum(x.value)})).filter(x=>x.value!==null&&wanted.test(x.label)).slice(0,10);
    if(pts.length>=3){const s={title:'Curva de aprendizagem • pontos brutos',points:pts};els.charts.innerHTML=`<article class="chart-card"><h3>${esc(s.title)}</h3><p>${esc(result.test)} • evolução entre tentativas</p>${svgLine(s)}</article>`;return;}
  }
  const candidates=result.tables.map(t=>({t,s:seriesFromTable(t)})).filter(x=>x.s); if(!candidates.length){els.charts.innerHTML='';return;}
  let chosen=candidates.slice(0,result.chart_type==='wechsler'?2:1); if(result.chart_type==='wechsler'){const comp=candidates.find(x=>/composto|qi/i.test(x.s.title));if(comp&&!chosen.includes(comp))chosen[1]=comp;}
  els.charts.innerHTML=chosen.map((x,i)=>{let svg;if(result.chart_type==='learning_curve')svg=svgLine(x.s);else if(result.chart_type==='domains')svg=svgRadar(x.s);else svg=svgBar(x.s);return `<article class="chart-card"><h3>${esc(x.s.title)}</h3><p>${esc(result.test)} • ${esc(result.chart_type.replace('_',' '))}</p>${svg}</article>`}).join('');
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
  try{const rep=await api('/api/ai/test-report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({patient:patient(),score_result:state.result,history:state.anamnesis})});state.testReports=state.testReports.filter(x=>x.teste!==rep.teste);state.testReports.push(rep);els.testReportOutput.innerHTML=renderStructured(rep);els.integratedBtn.disabled=false;toast('Laudo do teste gerado.');}catch(e){toast(e.message,true);}finally{els.testReportBtn.disabled=false;els.testReportBtn.textContent='Gerar laudo deste teste';}
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
  const fs=[...els.files.files];if(!fs.length)return;els.analyzeBtn.disabled=true;els.analyzeBtn.textContent='Lendo documentos…';
  try{const fd=new FormData();fd.append('patient_json',JSON.stringify(patient()));fs.forEach(f=>fd.append('files',f));const rep=await api('/api/ai/anamnesis',{method:'POST',body:fd});state.anamnesis=rep;els.anamnesisOutput.innerHTML=renderStructured(rep);els.integratedBtn.disabled=false;anamnesisAlert('Anamnese carregada — história de vida organizada com sucesso.','done');toast('História de vida organizada.');}catch(e){anamnesisAlert('Falha ao analisar a anamnese. Verifique os arquivos e tente novamente.','error');toast(e.message,true);}finally{els.analyzeBtn.disabled=false;els.analyzeBtn.textContent='Analisar e gerar história';}
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
  if(!state.results.length&&!state.anamnesis){toast('Calcule pelo menos um teste ou analise a anamnese.',true);return;}
  els.integratedBtn.disabled=true; const orig='Gerar Avaliação Completa';
  try{
    // 1) laudo de cada teste calculado que ainda não tem
    const pend=state.results.filter(r=>!state.testReports.some(x=>x.teste&&String(x.teste).toLowerCase().includes(String(r.test).toLowerCase())));
    for(let i=0;i<pend.length;i++){
      els.integratedBtn.textContent=`Laudo ${i+1}/${pend.length}: ${pend[i].test}…`;
      await ensureTestReport(pend[i]);
    }
    // 2) laudo geral com todos os testes
    els.integratedBtn.textContent='Integrando tudo…';
    const rep=await api('/api/ai/integrated-report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({patient:patient(),anamnesis:state.anamnesis,test_reports:state.testReports,raw_results:state.results,model:state.laudoModel})});
    state.integrated=rep;els.integratedOutput.innerHTML=renderStructured(rep);
    els.laudoActions.hidden=false;els.docxBtn.hidden=false;
    toast('Avaliação Neuropsicológica Completa gerada.');
    els.laudoActions.scrollIntoView({behavior:'smooth',block:'center'});
  }catch(e){toast(e.message,true);}finally{els.integratedBtn.disabled=false;els.integratedBtn.textContent=orig;}
});

// ---------- Salvar laudo integrado em .docx (Word) ----------
async function saveIntegratedDocx(btn){
  if(!state.integrated){toast('Gere a Avaliação Completa primeiro.',true);return;}
  const label=btn?btn.textContent:''; if(btn){btn.disabled=true;btn.textContent='Gerando .docx…';}
  try{
    const h={'Content-Type':'application/json'}; if(state.token) h['Authorization']=`Bearer ${state.token}`;
    const r=await fetch('/api/laudo/integrated-docx',{method:'POST',headers:h,
      body:JSON.stringify({patient:patient(),report:state.integrated,tests:state.results.map(x=>x.test)})});
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
body{font-family:Georgia,"Times New Roman",serif;max-width:760px;margin:40px auto;padding:0 24px;color:#1a1a1a;line-height:1.65}
h1{font-size:20px;border-bottom:2px solid #333;padding-bottom:8px;margin:0 0 16px}
h4{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#333;margin:20px 0 4px}
.meta{font-size:13px;color:#333;background:#f6f6f6;border:1px solid #e0e0e0;border-radius:8px;padding:12px 14px;margin-bottom:22px}
.ai-block{margin:0 0 4px}p{margin:4px 0}ul{margin:4px 0 4px 18px}
table{border-collapse:collapse;width:100%;margin:6px 0 14px;font-size:11px}
th,td{border:1px solid #bbb;padding:5px 7px;text-align:left;vertical-align:top}
th{background:#eef2f9;font-weight:700}
.tbl-cap{font-size:11px;font-weight:700;color:#333;margin:10px 0 2px}
.table-scroll{overflow-x:auto}
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

// ---------- Avaliações salvas (nuvem, por profissional) ----------
function evalPayload(){
  return {patient:patient(),results:state.results,anamnesis:state.anamnesis,
          test_reports:state.testReports,integrated_report:state.integrated,laudo_model:state.laudoModel};
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
  if(state.anamnesis){ els.anamnesisOutput.innerHTML=renderStructured(state.anamnesis); }
  if(state.laudoModel){ els.modelOutput.innerHTML=renderStructured(state.laudoModel); }
  if(state.integrated){
    els.integratedOutput.innerHTML=renderStructured(state.integrated);
    els.laudoActions.hidden=false; els.docxBtn.hidden=false;
  }
  if(state.results.length){
    state.result=state.results[state.results.length-1];
    renderResults(state.result); fillAutoFields(state.result);
    els.testReportBtn.disabled=!state.openaiConfigured; els.integratedBtn.disabled=!state.openaiConfigured;
  }
}

init();
