from __future__ import annotations

import asyncio
import logging
import time
import uuid
import json
import os
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Carrega o .env ANTES de importar módulos locais que leem env no import (auth).
ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')

from .workbook_engine import WorkbookEngine
from .openai_service import (analyze_anamnesis, analyze_anamnesis_form, analyze_laudo_model, extract_external_instrument,
                             generate_integrated_report, generate_test_report)
from .docx_report import build_integrated_docx, build_laudo_neuro_docx
from .file_content import to_content as file_to_content, accepted as file_accepted, FORMATS_LABEL
from . import auto_score
from .openai_service import generate_laudo_neuro, transcribe_corrected
from .ocr_prep import prepare_image
from . import auth, payments, store, scales, qplataforma, laudo_modelo, vineland, notify, recovery
from .auth import current_user

STATIC=ROOT/'static'
DB=ROOT/'data'/'neuro_normas.db'

log=logging.getLogger('neuroscore')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

# Documentação interativa da API (/docs, /redoc, /openapi.json) só quando pedida (dev).
_DOCS=os.getenv('ENABLE_API_DOCS','').lower() in ('1','true','yes')
app=FastAPI(title='NeuroScore API',version='1.1.0',
            docs_url='/docs' if _DOCS else None, redoc_url='/redoc' if _DOCS else None,
            openapi_url='/openapi.json' if _DOCS else None)
engine=WorkbookEngine(DB)
PUBLIC_URL=(os.getenv('PUBLIC_URL') or 'https://neuro-testes.appsbrasil.store').rstrip('/')

class ScoreRequest(BaseModel):
    test: str
    patient: dict[str,Any]=Field(default_factory=dict)
    raw_scores: dict[str,Any]=Field(default_factory=dict)
    parameters: dict[str,Any]=Field(default_factory=dict)

class TestReportRequest(BaseModel):
    patient: dict[str,Any]=Field(default_factory=dict)
    score_result: dict[str,Any]
    history: dict[str,Any]|None=None

class IntegratedRequest(BaseModel):
    patient: dict[str,Any]=Field(default_factory=dict)
    anamnesis: dict[str,Any]|None=None
    test_reports: list[dict[str,Any]]=Field(default_factory=list)
    raw_results: list[dict[str,Any]]=Field(default_factory=list)
    external_results: list[dict[str,Any]]=Field(default_factory=list)
    model: dict[str,Any]|None=None

class IntegratedDocxRequest(BaseModel):
    patient: dict[str,Any]=Field(default_factory=dict)
    report: dict[str,Any]
    tests: list[str]=Field(default_factory=list)
    charts: list[dict[str,Any]]=Field(default_factory=list)

class EvaluationRequest(BaseModel):
    patient: dict[str,Any]=Field(default_factory=dict)
    patient_id: str|None=None
    results: list[dict[str,Any]]=Field(default_factory=list)
    anamnesis: dict[str,Any]|None=None
    test_reports: list[dict[str,Any]]=Field(default_factory=list)
    integrated_report: dict[str,Any]|None=None
    laudo_model: dict[str,Any]|None=None
    external_results: list[dict[str,Any]]=Field(default_factory=list)

class ProfileRequest(BaseModel):
    full_name: str|None=None
    professional_id: str|None=None
    header: str|None=None
    default_model: dict[str,Any]|None=None
    avatar_url: str|None=None
    prefs: dict[str,Any]|None=None

class ProfessionalUpdate(BaseModel):
    full_name: str|None=None
    professional_id: str|None=None
    role: str|None=None
    status: str|None=None
    plan: str|None=None
    credits: float|None=None
    access: str|None=None        # 'admin' | 'pro' | 'trial'
    trial_days: int|None=None

class ProfessionalCreate(BaseModel):
    email: str
    password: str
    full_name: str|None=None
    professional_id: str|None=None
    role: str|None='professional'
    credits: float|None=0
    access: str|None=None        # 'admin' | 'pro' | 'trial'
    trial_days: int|None=None

class PlanUpsert(BaseModel):
    name: str|None=None
    credits: float|None=None
    amount_cents: int|None=None
    features: list[str]|None=None
    featured: bool|None=None
    active: bool|None=None
    sort: int|None=None

class PatientRequest(BaseModel):
    name: str|None=None
    birth_date: str|None=None
    sex: str|None=None
    education: str|None=None
    notes: str|None=None
    dados: dict[str,Any]|None=None
    anamnese: dict[str,Any]|None=None


async def active_user(user: dict = Depends(current_user)) -> dict:
    """Usuário logado E com acesso liberado (teste não expirado, conta não suspensa)."""
    if user.get('anon'):
        return user
    st = store.access_state(await store.get_profile(user))
    if st['blocked'] == 'trial_expired':
        raise HTTPException(403, 'trial_expired: seu período de teste terminou. Adquira créditos para continuar.')
    if st['blocked'] == 'suspended':
        raise HTTPException(403, 'suspended: sua conta está suspensa. Fale com o administrador.')
    if st['blocked'] == 'pending':
        raise HTTPException(403, 'pending: cadastro recebido. Aguarde o administrador liberar o seu acesso.')
    if st['blocked'] == 'rejected':
        raise HTTPException(403, 'rejected: seu cadastro não foi aprovado. Fale com o administrador.')
    return user


def _internal(msg: str, exc: Exception, code: int = 500) -> HTTPException:
    """Registra o erro completo no log e devolve ao usuário só uma mensagem limpa + código de suporte."""
    ref=uuid.uuid4().hex[:8]
    log.exception('%s [ref %s]', msg, ref, exc_info=exc)
    return HTTPException(code, f'{msg} Se persistir, informe ao suporte o código {ref}.')


def _slug(text: str) -> str:
    text=unicodedata.normalize('NFKD',text or '').encode('ascii','ignore').decode()
    text=re.sub(r'[^A-Za-z0-9]+','_',text).strip('_').lower()
    return text or 'paciente'

@app.get('/api/health')
def health():
    return {'ok':True,'tests':len(engine.list_tests())+len(scales.catalog_entries()),
            'openai_configured':bool(os.getenv('OPENAI_API_KEY')),
            'auth_enabled':auth.AUTH_ENABLED}

@app.get('/api/config')
def config():
    return auth.public_config()

@app.get('/api/tests')
def tests(user: dict = Depends(active_user)):
    return {'tests':engine.catalog() + scales.catalog_entries()}

@app.get('/api/tests/{test_name}')
def test_meta(test_name: str, user: dict = Depends(active_user)):
    name=unquote(test_name)
    if scales.is_scale(name):
        return scales.meta(name)
    try:
        return engine.test_meta(name)
    except KeyError:
        raise HTTPException(404,'Teste não encontrado')
    except Exception as exc:
        raise _internal('Falha ao preparar o teste.', exc)

def _score_ref(req: ScoreRequest) -> str:
    """Identifica "o mesmo teste do mesmo paciente" (recalcular no mesmo dia não cobra de novo)."""
    p=req.patient or {}
    who=_slug(str(p.get('name') or ''))+'|'+str(p.get('birth_date') or '')
    return f'{req.test}|{who}'[:300]

@app.post('/api/score')
async def score(req: ScoreRequest, user: dict = Depends(active_user)):
    # Cobra depois de corrigir: recalcular o mesmo teste no mesmo dia é grátis,
    # e quem decide isso é o spend_credits (402 se faltar saldo).
    charge=auth.AUTH_ENABLED
    try:
        if scales.is_scale(req.test):
            result=scales.score(req.test,req.patient,req.raw_scores,req.parameters)
        else:
            result=await run_in_threadpool(engine.score,req.test,req.patient,req.raw_scores,req.parameters)
    except KeyError as exc:
        raise HTTPException(404,str(exc))
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    except Exception as exc:
        raise _internal('Erro ao corrigir o teste.', exc)
    if charge:
        result['credits_balance']=await store.spend_credits(user, store.COST_TESTE, 'teste', _score_ref(req))
    return result

@app.post('/api/ai/test-report')
def ai_test_report(req: TestReportRequest, user: dict = Depends(active_user)):
    try:
        return generate_test_report(req.patient,req.score_result,req.history)
    except Exception as exc:
        raise HTTPException(502,str(exc))

@app.post('/api/ai/anamnesis')
async def ai_anamnesis(patient_json: str=Form('{}'), files: list[UploadFile]=File(...), patient_id: str|None=Form(None),
                       user: dict = Depends(active_user)):
    try:
        patient=json.loads(patient_json or '{}')
    except json.JSONDecodeError:
        raise HTTPException(400,'patient_json inválido')
    parsed=[]
    total=0
    for f in files:
        data=await f.read()
        total+=len(data)
        if len(data)>25*1024*1024:
            raise HTTPException(413,f'{f.filename}: arquivo acima de 25 MB')
        mime=f.content_type or 'application/octet-stream'
        if not file_accepted(f.filename or '',mime):
            raise HTTPException(415,f'{f.filename}: formato não suportado (use {FORMATS_LABEL})')
        if (f.filename or '').lower().endswith('.pdf') and not mime.startswith('image/'):
            mime='application/pdf'
        parsed.append((f.filename or 'arquivo',mime,data))
    if total>45*1024*1024:
        raise HTTPException(413,'Total de anexos acima de 45 MB')
    if auth.AUTH_ENABLED and not await store.can_spend(user, store.COST_HISTORIA):
        raise HTTPException(402, store.NO_CREDITS.format(need='1'))
    try:
        rep=await run_in_threadpool(analyze_anamnesis,parsed,patient)
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    except Exception as exc:
        raise HTTPException(502,str(exc))
    if auth.AUTH_ENABLED:
        await store.spend_credits(user, store.COST_HISTORIA, 'historia')
        # entra em "Testes realizados" do paciente (nome/nascimento lidos da anamnese se faltarem)
        ident=rep.get('identificacao') or {}
        p={**patient}
        if not str(p.get('name') or '').strip() and ident.get('nome'):
            p['name']=ident['nome'].strip()
        if not p.get('birth_date') and re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(ident.get('data_nascimento') or '')):
            p['birth_date']=ident['data_nascimento']
        try:
            rec=await store.save_test_result(user,{'patient':p,'patient_id':patient_id or None,'test':store.HISTORIA_TEST,
                                                  'inputs':{'arquivos':[n for n,_,_ in parsed]},'result':rep})
            rep={**rep,'_registro':{'id':rec.get('id'),'patient':p}}
        except Exception as exc:
            rep={**rep,'_registro':{'erro':str(getattr(exc,'detail',exc))}}
    return rep

class AnamnesisFormRequest(BaseModel):
    patient: dict[str,Any]=Field(default_factory=dict)
    patient_id: str|None=None
    respostas: dict[str,Any]=Field(default_factory=dict)   # id do campo → valor marcado
    texto: str                                              # respostas já legíveis (rótulo: valor)

@app.post('/api/ai/anamnesis-form')
async def ai_anamnesis_form(req: AnamnesisFormRequest, user: dict = Depends(active_user)):
    """Anamnese preenchida por marcação → história de vida organizada (1 crédito)."""
    texto=req.texto.strip()[:30000]
    if len(texto)<20:
        raise HTTPException(400,'Marque as respostas da anamnese antes de gerar a história.')
    if auth.AUTH_ENABLED and not await store.can_spend(user, store.COST_HISTORIA):
        raise HTTPException(402, store.NO_CREDITS.format(need='1'))
    try:
        rep=await run_in_threadpool(analyze_anamnesis_form,texto,req.patient)
    except Exception as exc:
        raise HTTPException(502,str(exc))
    rep={'transcricao':[{'documento':'Anamnese Infantojuvenil (formulário)','pagina':'1','texto':texto}],**rep}
    if auth.AUTH_ENABLED:
        await store.spend_credits(user, store.COST_HISTORIA, 'historia')
        try:
            rec=await store.save_test_result(user,{'patient':req.patient,'patient_id':req.patient_id,'test':store.HISTORIA_TEST,
                                                  'inputs':{'formulario':req.respostas},'result':rep})
            rep={**rep,'_registro':{'id':rec.get('id'),'patient':req.patient}}
        except Exception as exc:
            rep={**rep,'_registro':{'erro':str(getattr(exc,'detail',exc))}}
    return rep

@app.post('/api/ai/laudo-model')
async def ai_laudo_model(files: list[UploadFile]=File(...), user: dict = Depends(active_user)):
    parsed=[]
    total=0
    allowed_ext=('.pdf','.doc','.docx','.txt','.md','.rtf','.odt')
    for f in files:
        data=await f.read()
        total+=len(data)
        if len(data)>15*1024*1024:
            raise HTTPException(413,f'{f.filename}: arquivo acima de 15 MB')
        mime=f.content_type or 'application/octet-stream'
        name=(f.filename or 'modelo')
        if not (mime=='application/pdf' or mime.startswith('image/') or mime.startswith('text/')
                or name.lower().endswith(allowed_ext)):
            raise HTTPException(415,f'{name}: envie PDF, DOCX, TXT ou imagem')
        parsed.append((name,mime,data))
    if total>30*1024*1024:
        raise HTTPException(413,'Total de anexos acima de 30 MB')
    try:
        return analyze_laudo_model(parsed)
    except Exception as exc:
        raise HTTPException(502,str(exc))

@app.post('/api/ai/external-instrument')
async def ai_external_instrument(nome: str=Form(''), files: list[UploadFile]=File(...),
                                 user: dict = Depends(active_user)):
    parsed=[]
    total=0
    for f in files:
        data=await f.read()
        total+=len(data)
        if len(data)>20*1024*1024:
            raise HTTPException(413,f'{f.filename}: arquivo acima de 20 MB')
        mime=f.content_type or 'application/octet-stream'
        name=(f.filename or 'arquivo')
        if not (mime=='application/pdf' or mime.startswith('image/') or mime.startswith('text/')
                or name.lower().endswith(('.pdf','.txt','.md','.csv'))):
            raise HTTPException(415,f'{name}: envie PDF, imagem ou texto')
        parsed.append((name,mime,data))
    if total>40*1024*1024:
        raise HTTPException(413,'Total de anexos acima de 40 MB')
    try:
        return extract_external_instrument(parsed, nome)
    except Exception as exc:
        raise HTTPException(502,str(exc))

@app.post('/api/ai/integrated-report')
async def ai_integrated(req: IntegratedRequest, user: dict = Depends(active_user)):
    if auth.AUTH_ENABLED and not await store.can_laudo(user):
        raise HTTPException(402, store.NO_CREDITS.format(need='1'))
    try:
        report = await run_in_threadpool(
            generate_integrated_report, req.patient, req.anamnesis,
            req.test_reports, req.raw_results, req.model, req.external_results)
    except Exception as exc:
        raise HTTPException(502, str(exc))
    if auth.AUTH_ENABLED:
        try:
            await store.spend_laudo(user, (req.patient or {}).get('name'))
        except HTTPException:
            raise
        except Exception:
            pass
    return report

# ---------------- Geração de Laudo Neuropsicológico (aba dedicada) ----------------
# ---- tarefas longas em segundo plano ----
# A Cloudflare corta respostas que passam de 100 s (erro 524). Laudo e upload de testes levam mais
# que isso: o navegador inicia a tarefa (/start), recebe um id na hora e consulta /api/jobs/{id}.
_JOBS: dict[str, dict] = {}


class _MemFile:
    """Arquivo já lido (o UploadFile original fecha quando a requisição termina)."""
    def __init__(self, filename: str, content_type: str, data: bytes):
        self.filename, self.content_type, self._data = filename, content_type, data

    async def read(self) -> bytes:
        return self._data


MAX_FILE_MB=int(os.getenv('MAX_FILE_MB','25'))
MAX_FILES=int(os.getenv('MAX_FILES','30'))


async def _mem(files: list[UploadFile]) -> list[_MemFile]:
    files=files or []
    if len(files) > MAX_FILES:
        raise HTTPException(413, f'Envie no máximo {MAX_FILES} arquivos por vez.')
    out=[]
    for f in files:
        data=await f.read()
        if len(data) > MAX_FILE_MB*1024*1024:
            raise HTTPException(413, f'O arquivo "{f.filename}" passa de {MAX_FILE_MB} MB. Reduza a resolução ou divida o PDF.')
        out.append(_MemFile(f.filename or 'arquivo', f.content_type or '', data))
    return out


def _start_job(user: dict, make_coro) -> dict:
    now = time.time()
    for k in [k for k, j in _JOBS.items() if now - j['t'] > 3 * 3600]:
        _JOBS.pop(k, None)
    jid = uuid.uuid4().hex
    job = {'owner': user.get('id'), 't': now, 'status': 'running'}
    _JOBS[jid] = job

    async def run():
        try:
            job.update(status='done', result=await make_coro())
        except HTTPException as exc:
            job.update(status='error', code=exc.status_code, detail=str(exc.detail))
        except Exception as exc:
            e=_internal('A tarefa falhou inesperadamente.', exc)
            job.update(status='error', code=500, detail=e.detail)

    job['task'] = asyncio.create_task(run())
    return {'job': jid}


@app.get('/api/jobs/{jid}')
async def job_status(jid: str, user: dict = Depends(active_user)):
    job = _JOBS.get(jid)
    if not job or job['owner'] != user.get('id'):
        raise HTTPException(404, 'Tarefa não encontrada (o servidor pode ter sido reiniciado). Tente de novo.')
    if job['status'] == 'done':
        return {'status': 'done', 'result': job['result'], 'elapsed': round(time.time() - job['t'])}
    if job['status'] == 'error':
        return {'status': 'error', 'code': job.get('code', 500), 'detail': job.get('detail', '')}
    return {'status': 'running', 'elapsed': round(time.time() - job['t'])}


@app.post('/api/ai/laudo-neuro/start')
async def ai_laudo_neuro_start(dados_json: str=Form('{}'), files: list[UploadFile]=File(default=[]),
                               anamnese_files: list[UploadFile]=File(default=[]),
                               user: dict = Depends(active_user)):
    fs, an = await _mem(files), await _mem(anamnese_files)
    return _start_job(user, lambda: ai_laudo_neuro(dados_json=dados_json, files=fs, anamnese_files=an, user=user))


@app.post('/api/test-results/import/start')
async def test_results_import_start(patient_json: str=Form('{}'), patient_id: str|None=Form(None),
                                    files: list[UploadFile]=File(...), user: dict = Depends(active_user)):
    fs = await _mem(files)
    return _start_job(user, lambda: test_results_import(patient_json=patient_json, patient_id=patient_id,
                                                        files=fs, user=user))


@app.post('/api/ai/laudo-neuro')
async def ai_laudo_neuro(dados_json: str=Form('{}'), files: list[UploadFile]=File(default=[]),
                         anamnese_files: list[UploadFile]=File(default=[]),
                         user: dict = Depends(active_user)):
    try:
        dados=json.loads(dados_json or '{}')
    except json.JSONDecodeError:
        raise HTTPException(400,'dados_json inválido')
    groups=[]
    total=0
    for f in files:
        data=await f.read()
        total+=len(data)
        if len(data)>25*1024*1024:
            raise HTTPException(413,f'{f.filename}: arquivo acima de 25 MB')
        try:
            groups.append((f.filename or 'arquivo', file_to_content(f.filename or 'arquivo', f.content_type or '', data)))
        except ValueError as exc:
            raise HTTPException(415,str(exc))
        except Exception as exc:
            raise HTTPException(422,f'{f.filename}: não foi possível ler o arquivo ({type(exc).__name__})')
    # anamnese: só para a história de vida (seção 06) — não passa pela triagem/motor
    anamnese_items=[]
    anamnese_ocr=[]   # PDF/foto → OCR da História de Vida (vai para Testes realizados)
    for f in anamnese_files:
        data=await f.read()
        total+=len(data)
        if len(data)>25*1024*1024:
            raise HTTPException(413,f'{f.filename}: arquivo acima de 25 MB')
        mime=f.content_type or 'application/octet-stream'
        if not file_accepted(f.filename or '',mime):
            raise HTTPException(415,f'{f.filename}: formato não suportado (use {FORMATS_LABEL})')
        if (f.filename or '').lower().endswith('.pdf') and not mime.startswith('image/'):
            mime='application/pdf'
        anamnese_ocr.append((f.filename or 'anamnese',mime,data))
    if total>60*1024*1024:
        raise HTTPException(413,'Total de anexos acima de 60 MB')
    if str(dados.get('escores_digitados') or '').strip():
        groups.append(('escores_digitados.txt', [{'type': 'input_text', 'text':
            '--- Arquivo: escores_digitados.txt ---\n' + str(dados['escores_digitados'])}]))
    items=[it for _, its in groups for it in its]
    # Testes realizados (já corrigidos pelo motor e salvos) + História de Vida salva do paciente
    salvos=[]
    ids=[str(x) for x in (dados.pop('testes_realizados_ids', None) or [])][:40]
    if ids and auth.AUTH_ENABLED:
        recs={r['id']:r for r in await store.list_test_results(user)}
        for rid in ids:
            r=recs.get(rid)
            if not r:
                continue
            if r.get('test')==store.HISTORIA_TEST:
                res=r.get('result') or {}
                dados['historia_de_vida_salva']={'historia_modelo':res.get('historia_modelo'),'resumo':res.get('resumo'),
                                                 'historia_de_vida':res.get('historia_de_vida')}
            elif (r.get('result') or {}).get('tables'):
                salvos.append({'teste':vineland.display_name(r['test']),'origem':'Testes realizados (corrigido pelo NeuroScore)',
                               'escores_brutos_usados':vineland.split_inputs((r.get('inputs') or {}).get('raw_scores') or {}),
                               'tabelas_corrigidas':auto_score._compact(r['result']['tables'])})
    if dados.get('tipo_laudo')=='teste_isolado':
        dados['instrucao_tipo_laudo']=('LAUDO DE TESTE ISOLADO: mesmo modelo, mas a análise, a conclusão e as '
                                       'recomendações tratam só do(s) instrumento(s) enviado(s); não generalize '
                                       'para um diagnóstico global — indique que outros instrumentos complementam.')
    if not items and not salvos and not str(dados.get('escores_digitados') or '').strip():
        raise HTTPException(400,'Envie os arquivos dos testes, escolha testes realizados ou digite os escores.')
    if auth.AUTH_ENABLED and not await store.can_laudo(user):
        raise HTTPException(402, store.NO_CREDITS.format(need='1'))
    # 1) em paralelo: OCR da anamnese (→ História de Vida) e correção pelo motor dos testes com escores brutos
    pac=dados.pop('paciente_motor', None) or {}
    alertas_correcao, corrigidos, salvos_agora = [], [], []
    async def _corrigir():
        if not groups:
            return [], []
        try:
            c, _triagem, al = await run_in_threadpool(auto_score.run, engine, groups, pac)
            return c, al
        except Exception as exc:
            return [], [f'Correção automática indisponível ({type(exc).__name__}); '
                        'o laudo usou só os escores já corrigidos nos arquivos.']
    async def _ocr():
        if not anamnese_ocr:
            return None
        try:
            p={'name':pac.get('name'),'birth_date':pac.get('birth_date'),'sex':pac.get('sex')}
            return await run_in_threadpool(analyze_anamnesis, anamnese_ocr, p)
        except Exception as exc:
            alertas_correcao.append(f'Leitura (OCR) da anamnese falhou ({type(exc).__name__}); '
                                    'o laudo usou os arquivos diretamente.')
            return None
    (corrigidos, al), hv = await asyncio.gather(_corrigir(), _ocr())
    alertas_correcao += al
    if anamnese_ocr and hv is None:
        for n, m, d in anamnese_ocr:
            try:
                anamnese_items += file_to_content(n, m, d)
            except Exception:
                alertas_correcao.append(f'{n}: não foi possível ler o arquivo da anamnese.')
    pac_rec={k: pac.get(k) for k in ('name','birth_date','application_date','sex','education') if pac.get(k)}
    gravar=auth.AUTH_ENABLED and bool(pac_rec.get('name'))
    if hv:
        dados['historia_de_vida_salva']={'historia_modelo':hv.get('historia_modelo'),'resumo':hv.get('resumo'),
                                         'historia_de_vida':hv.get('historia_de_vida')}
        if gravar:
            try:
                await store.save_test_result(user,{'patient':pac_rec,'patient_id':dados.get('patient_id'),'test':store.HISTORIA_TEST,
                                                  'inputs':{'arquivos':[n for n,_,_ in anamnese_ocr]},'result':hv})
                salvos_agora.append(store.HISTORIA_TEST)
            except Exception:
                alertas_correcao.append('A História de Vida não pôde ser salva em Testes realizados.')
    for c in corrigidos:
        raw, res = c.pop('_raw', {}), c.pop('_resultado', None)
        if gravar and res and res.get('tables'):
            try:
                await store.save_test_result(user,{'patient':pac_rec,'patient_id':dados.get('patient_id'),'test':c['teste'],
                                                  'inputs':{'raw_scores':raw,'parameters':{}},'result':res})
                salvos_agora.append(c['teste'])
            except Exception:
                alertas_correcao.append(f"{c['teste']}: não pôde ser salvo em Testes realizados.")
    if corrigidos or salvos:
        dados['resultados_corrigidos_pelo_sistema'] = salvos + corrigidos
    # 2) laudo
    try:
        laudo=await run_in_threadpool(generate_laudo_neuro, dados, items, anamnese_items)
    except Exception as exc:
        raise HTTPException(502,str(exc))
    laudo['alertas_para_revisao'] = alertas_correcao + list(laudo.get('alertas_para_revisao') or [])
    laudo['textos_fixos'] = laudo_modelo.textos_fixos((laudo.get('identificacao') or {}).get('nome_paciente')
                                                      or (dados.get('identificacao') or {}).get('nome'))
    laudo['correcao_automatica'] = [{'teste': c['teste'], 'escores_brutos_usados': c['escores_brutos_usados']}
                                    for c in corrigidos]
    # relatórios já corrigidos (ex.: Pearson) também vão para Testes realizados, com as tabelas transcritas
    if gravar:
        def _norm(x):
            return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',str(x or '')).encode('ascii','ignore').decode().lower())
        ja=[_norm(n) for n in salvos_agora+[x['teste'] for x in salvos] if n!=store.HISTORIA_TEST]
        for t in laudo.get('analise_testes') or []:
            nome=str(t.get('instrumento') or '').strip()
            tabs=[tb for tb in t.get('tabelas') or [] if tb.get('colunas') and tb.get('linhas')]
            if not nome or not tabs or any(j and (j in _norm(nome) or _norm(nome) in j) for j in ja):
                continue
            res={'test':nome,'externo':True,'interpretacao':t.get('interpretacao'),
                 'tables':[{'title':tb.get('titulo') or nome,'columns':[{'label':c} for c in tb['colunas']],
                            'rows':[{'values':r} for r in tb['linhas']]} for tb in tabs]}
            try:
                await store.save_test_result(user,{'patient':pac_rec,'patient_id':dados.get('patient_id'),'test':nome,
                                                  'inputs':{'arquivos':[n for n,_ in groups]},'result':res})
                salvos_agora.append(nome)
            except Exception:
                pass
    laudo['salvos_em_testes_realizados'] = salvos_agora
    if auth.AUTH_ENABLED:
        try:
            await store.spend_laudo(user, (dados.get('identificacao') or {}).get('nome'))
        except HTTPException:
            raise
        except Exception:
            pass
    return laudo

@app.post('/api/test-results/import')
async def test_results_import(patient_json: str=Form('{}'), patient_id: str|None=Form(None),
                              files: list[UploadFile]=File(...), user: dict = Depends(active_user)):
    """Testes realizados → upload: lê os arquivos (OCR), identifica os testes e salva cada um.
    Escores brutos de teste do catálogo → corrigidos pelo motor (1 crédito por teste, como em Laudos).
    Relatório já corrigido → tabelas transcritas, sem custo."""
    try:
        patient=json.loads(patient_json or '{}')
    except json.JSONDecodeError:
        raise HTTPException(400,'patient_json inválido')
    pac={k: patient.get(k) for k in ('name','birth_date','application_date','sex','education') if patient.get(k)}
    if not str(pac.get('name') or '').strip():
        raise HTTPException(400,'Informe o nome do paciente.')
    groups, nomes, total = [], [], 0
    for f in files:
        data=await f.read()
        total+=len(data)
        name=f.filename or 'arquivo'
        mime=f.content_type or ''
        if len(data)>25*1024*1024:
            raise HTTPException(413,f'{name}: arquivo acima de 25 MB')
        if not file_accepted(name,mime):
            raise HTTPException(415,f'{name}: formato não suportado (use {FORMATS_LABEL})')
        try:
            if mime.startswith('image/'):
                data,mime=prepare_image(data,mime)
            groups.append((name, file_to_content(name, mime, data)))
        except ValueError as exc:
            raise HTTPException(415,str(exc))
        except Exception as exc:
            raise HTTPException(422,f'{name}: não foi possível ler o arquivo ({type(exc).__name__})')
        nomes.append(name)
    if total>60*1024*1024:
        raise HTTPException(413,'Total de anexos acima de 60 MB')
    if auth.AUTH_ENABLED and not await store.can_spend(user, store.COST_TESTE):
        raise HTTPException(402, store.NO_CREDITS.format(need='1'))
    try:
        corrigidos, triagem, alertas = await run_in_threadpool(auto_score.run, engine, groups, pac)
    except Exception as exc:
        raise HTTPException(502,f'Não foi possível ler os arquivos: {exc}')
    salvos=[]
    async def _save(test, inputs, res):
        rec=await store.save_test_result(user,{'patient':pac,'patient_id':patient_id or None,'test':test,
                                              'inputs':inputs,'result':res})
        salvos.append({'id':rec.get('id'),'test':test,'patient_key':rec.get('patient_key')})
    for c in corrigidos:
        raw, res = c.pop('_raw', {}), c.pop('_resultado', None)
        if not (res and res.get('tables')):
            continue
        if auth.AUTH_ENABLED:
            who=_slug(str(pac.get('name') or ''))+'|'+str(pac.get('birth_date') or '')
            try:
                await store.spend_credits(user, store.COST_TESTE, 'teste', f"{c['teste']}|{who}"[:300])
            except HTTPException as exc:
                if exc.status_code==402:
                    alertas.append(f"{c['teste']}: créditos insuficientes para corrigir; não foi salvo.")
                    continue
                raise
        await _save(c['teste'], {'raw_scores':raw,'parameters':{},'arquivos':nomes}, res)
    prontos=[t for t in triagem if t.get('situacao')=='corrigido']
    if prontos:
        try:
            tr=await run_in_threadpool(transcribe_corrected, [it for _, its in groups for it in its],
                                       [t.get('instrumento') or t.get('teste_catalogo') for t in prontos])
        except Exception as exc:
            tr={'instrumentos':[]}
            alertas.append(f'Não foi possível transcrever os relatórios já corrigidos ({type(exc).__name__}).')
        for t in tr.get('instrumentos') or []:
            tabs=[tb for tb in t.get('tabelas') or [] if tb.get('colunas') and tb.get('linhas')]
            nome=str(t.get('instrumento') or '').strip()
            if not nome or not tabs:
                continue
            res={'test':nome,'externo':True,'interpretacao':t.get('observacoes') or '',
                 'tables':[{'title':tb.get('titulo') or nome,'columns':[{'label':x} for x in tb['colunas']],
                            'rows':[{'values':r} for r in tb['linhas']]} for tb in tabs]}
            await _save(nome, {'arquivos':nomes}, res)
    if not salvos and not alertas:
        alertas.append('Nenhum teste com escores foi encontrado nos arquivos.')
    return {'salvos':salvos,'alertas':alertas,'patient_key':store.patient_key(pac),
            'triagem':[{k:t.get(k) for k in ('instrumento','teste_catalogo','situacao')} for t in triagem]}


class LaudoNeuroDocxRequest(BaseModel):
    laudo: dict[str,Any]
    charts: list[dict[str,Any]]=Field(default_factory=list)

@app.post('/api/laudo/neuro-docx')
def laudo_neuro_docx(req: LaudoNeuroDocxRequest, user: dict = Depends(active_user)):
    try:
        data=build_laudo_neuro_docx(req.laudo,req.charts)
    except Exception as exc:
        raise _internal('Falha ao gerar o arquivo .docx.', exc)
    nome=(req.laudo.get('identificacao') or {}).get('nome_paciente','')
    name=f"laudo_neuropsicologico_{_slug(nome)}_{date.today().isoformat()}.docx"
    return Response(
        content=data,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={'Content-Disposition': f'attachment; filename="{name}"'},
    )

@app.post('/api/laudo/integrated-docx')
def laudo_integrated_docx(req: IntegratedDocxRequest, user: dict = Depends(active_user)):
    if not req.report:
        raise HTTPException(400,'Gere o laudo integrado antes de exportar.')
    try:
        data=build_integrated_docx(req.patient,req.report,req.tests,req.charts)
    except Exception as exc:
        raise _internal('Falha ao gerar o arquivo .docx.', exc)
    name=f"avaliacao_neuropsicologica_completa_{_slug(req.patient.get('name',''))}_{date.today().isoformat()}.docx"
    return Response(
        content=data,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={'Content-Disposition': f'attachment; filename=\"{name}\"'},
    )

# ---------------- Avaliações salvas (Supabase) ----------------
@app.get('/api/evaluations')
async def evaluations_list(patient: str | None = None, user: dict = Depends(active_user)):
    return {'evaluations': await store.list_evaluations(user, patient)}

@app.get('/api/evaluations/{eval_id}')
async def evaluations_get(eval_id: str, user: dict = Depends(active_user)):
    return await store.get_evaluation(user, eval_id)

@app.post('/api/evaluations')
async def evaluations_create(req: EvaluationRequest, user: dict = Depends(active_user)):
    return await store.save_evaluation(user, req.model_dump())

@app.put('/api/evaluations/{eval_id}')
async def evaluations_update(eval_id: str, req: EvaluationRequest, user: dict = Depends(active_user)):
    return await store.save_evaluation(user, req.model_dump(), eval_id)

@app.delete('/api/evaluations/{eval_id}')
async def evaluations_delete(eval_id: str, user: dict = Depends(active_user)):
    await store.delete_evaluation(user, eval_id)
    return {'ok': True}

@app.get('/api/profile')
async def profile_get(request: Request, user: dict = Depends(current_user)):
    # Liberado mesmo com o teste expirado: o app usa para mostrar o bloqueio e o contador.
    p = await store.get_profile(user)
    ip = client_ip(request)
    patch: dict[str, Any] = {}
    if ip and ip != p.get('last_ip'):
        patch.update(last_ip=ip, last_ip_at='now()')
    if ip and not p.get('signup_ip') and p.get('status') == 'pending':
        # cadastro feito antes do registro de IP (ou o aviso do navegador falhou): usa o IP do 1º acesso
        patch.update(signup_ip=ip, signup_ip_at='now()', signup_user_agent=(request.headers.get('user-agent') or '')[:300])
    if patch:
        patch = {k: (_now_iso() if v == 'now()' else v) for k, v in patch.items()}
        try:
            await store._service_req('PATCH', '/profiles', params={'id': f'eq.{p["id"]}'}, json=patch)
            p.update(patch)
        except Exception as exc:  # registro de IP nunca quebra o login
            log.warning('Registro de IP falhou: %s', exc)
    if p.get('status') == 'pending' and not (p.get('prefs') or {}).get('_admin_notified') and notify.enabled():
        asyncio.create_task(_notify_signup(p))
    return {**p, 'access': store.access_state(p)}


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def client_ip(request: Request) -> str:
    """IP real de quem fez a requisição. O site passa pela Cloudflare (CF-Connecting-IP);
    depois pelo Traefik (X-Forwarded-For, o primeiro da lista é o cliente)."""
    ip = (request.headers.get('cf-connecting-ip') or request.headers.get('x-real-ip') or '').strip()
    if not ip:
        ip = (request.headers.get('x-forwarded-for') or '').split(',')[0].strip()
    if not ip and request.client:
        ip = request.client.host
    return re.sub(r'[^0-9a-fA-F:.]', '', ip)[:64]


async def same_ip_accounts(pid: str, ip: str | None) -> list[dict]:
    """Outras contas cujo IP do cadastro ou do último acesso é igual a `ip`."""
    ip = re.sub(r'[^0-9a-fA-F:.]', '', ip or '')
    if not ip:
        return []
    rows = await store._service_req('GET', '/profiles', params={
        'select': 'id,full_name,email,status',
        'or': f'(signup_ip.eq."{ip}",last_ip.eq."{ip}")', 'id': f'neq.{pid}', 'limit': '20'}) or []
    return rows


def _fmt_same_ip(rows: list[dict]) -> str:
    st = {'pending': 'aguardando', 'rejected': 'recusado', 'suspended': 'suspenso'}
    return '\n'.join(f'• {r.get("full_name") or "—"} ({r.get("email") or "—"}) — {st.get(r.get("status"), "ativo")}'
                     for r in rows[:10])


async def _alert_same_ip(pid: str, ip: str, who: dict) -> None:
    """Aviso imediato ao admin: cadastro novo vindo de um IP que já tem outra conta."""
    try:
        others = await same_ip_accounts(pid, ip)
        if not others or not notify.enabled():
            return
        await notify.notify_admin(
            '⚠️ *NeuroScore — ALERTA: cadastro do mesmo IP*\n\n'
            f'Novo pedido: {who.get("full_name") or "—"} ({who.get("email") or "—"})\nIP: {ip}\n\n'
            f'Já existe(m) conta(s) com este IP:\n{_fmt_same_ip(others)}\n\n'
            f'Confira antes de aprovar: {PUBLIC_URL}/app#admin')
    except Exception as exc:
        log.warning('Alerta de IP repetido falhou: %s', exc)


class SignupIp(BaseModel):
    user_id: str


@app.post('/api/auth/signup-ip')
async def signup_ip(req: SignupIp, request: Request):
    """Chamado pelo login.html logo depois do signUp: grava o IP de quem pediu a liberação.
    Só vale para cadastro pendente, criado há menos de 15 min e ainda sem IP."""
    _rate_limit(request, 'signup-ip', 20)
    if not re.fullmatch(r'[0-9a-fA-F-]{36}', req.user_id or ''):
        return {'ok': False}
    try:
        rows = await store._service_req('GET', '/profiles', params={
            'id': f'eq.{req.user_id}', 'select': 'id,full_name,email,status,signup_ip,created_at', 'limit': '1'}) or []
        r = rows[0] if rows else None
        if not r or r.get('status') != 'pending' or r.get('signup_ip'):
            return {'ok': False}
        from datetime import datetime, timezone
        created = datetime.fromisoformat(str(r['created_at']).replace('Z', '+00:00'))
        if (datetime.now(timezone.utc) - created).total_seconds() > 900:
            return {'ok': False}
        ip = client_ip(request)
        await store._service_req('PATCH', '/profiles', params={'id': f'eq.{r["id"]}', 'signup_ip': 'is.null'}, json={
            'signup_ip': ip, 'signup_ip_at': _now_iso(),
            'signup_user_agent': (request.headers.get('user-agent') or '')[:300]})
        asyncio.create_task(_alert_same_ip(r['id'], ip, r))
        return {'ok': True}
    except Exception as exc:
        log.warning('IP do cadastro falhou: %s', exc)
        return {'ok': False}


async def _notify_signup(p: dict) -> None:
    """Avisa o admin no WhatsApp, uma única vez, que há cadastro aguardando aprovação."""
    try:
        prefs = {**(p.get('prefs') or {}), '_admin_notified': True}
        await store._service_req('PATCH', '/profiles', params={'id': f'eq.{p["id"]}'}, json={'prefs': prefs})
        ip = p.get('signup_ip') or p.get('last_ip')
        others = await same_ip_accounts(p['id'], ip)
        alerta = (f'⚠️ *ALERTA: mesmo IP de outra(s) conta(s):*\n{_fmt_same_ip(others)}\n\n' if others else '')
        await notify.notify_admin(
            ('⚠️ ' if others else '🆕 ') + '*NeuroScore — novo cadastro aguardando aprovação*\n\n'
            f'Nome: {p.get("full_name") or "—"}\nCRP: {p.get("professional_id") or "—"}\n'
            f'E-mail: {p.get("email") or "—"}\nWhatsApp: {p.get("phone") or "—"}\nCidade: {p.get("city") or "—"}\n'
            f'IP do pedido: {ip or "—"}\n\n' + alerta +
            f'Aprovar: {PUBLIC_URL}/app#admin')
    except Exception as exc:  # aviso nunca quebra o login
        log.warning('Aviso de cadastro falhou: %s', exc)


# ---------- recuperação de senha por WhatsApp (público, com limite por IP) ----------
_RL: dict[str, list[float]] = {}

def _rate_limit(request: Request, bucket: str, limit: int, window: int = 3600) -> None:
    ip = client_ip(request) or '?'
    k, now = f'{bucket}:{ip}', time.time()
    hits = [t for t in _RL.get(k, []) if now - t < window]
    if len(hits) >= limit:
        raise HTTPException(429, 'Muitas tentativas. Aguarde alguns minutos e tente de novo.')
    hits.append(now); _RL[k] = hits
    if len(_RL) > 5000:
        _RL.clear()

class ResetStart(BaseModel):
    email: str

class ResetConfirm(BaseModel):
    email: str
    code: str
    password: str

_WA_OK: dict[str, float] = {}

async def _whatsapp_ready() -> bool:
    """WhatsApp configurado E conectado (cache de 60 s para não consultar a cada clique)."""
    if not recovery.available():
        return False
    now = time.time()
    if now - _WA_OK.get('t', 0) > 60:
        st = (await notify.connection_state()).get('state')
        _WA_OK.update(t=now, ok=1.0 if st in (None, 'open') else 0.0)
    return bool(_WA_OK.get('ok'))

@app.get('/api/auth/recovery')
async def recovery_options():
    # e-mail: link pelo Supabase Auth (SMTP configurado no serviço de login); EMAIL_RECOVERY=0 desliga
    return {'whatsapp': await _whatsapp_ready(), 'email': os.getenv('EMAIL_RECOVERY', '1') not in ('0', 'false', 'no')}

@app.post('/api/auth/reset/start')
async def reset_start(req: ResetStart, request: Request):
    _rate_limit(request, 'reset-start', 8)
    return await recovery.start(req.email)

@app.post('/api/auth/reset/confirm')
async def reset_confirm(req: ResetConfirm, request: Request):
    _rate_limit(request, 'reset-confirm', 20)
    return await recovery.confirm(req.email, req.code, req.password)


# ---------- status do sistema (card no Admin) ----------
@app.get('/api/admin/status')
async def admin_status(user: dict = Depends(active_user)):
    await store._require_admin(user)
    out: dict[str, Any] = {'app': {'ok': True, 'version': app.version},
                           'openai': bool(os.getenv('OPENAI_API_KEY')),
                           'payments': payments.enabled(), 'whatsapp': notify.enabled(),
                           'recovery_whatsapp': recovery.available(),
                           'smtp': os.getenv('EMAIL_RECOVERY', '1') not in ('0', 'false', 'no')}
    try:
        t0 = time.time()
        rows = await store._service_req('GET', '/profiles', params={'select': 'status'}) or []
        out['db'] = {'ok': True, 'ms': round((time.time() - t0) * 1000)}
        out['pending'] = sum(1 for r in rows if r.get('status') == 'pending')
        out['users'] = len(rows)
    except Exception as exc:
        out['db'] = {'ok': False, 'error': str(exc)[:120]}
    out['whatsapp_conn'] = await notify.connection_state() if notify.enabled() else {}
    try:
        st = await store._service_req('GET', '/system_status', params={'select': 'key,value,updated_at'}) or []
        out['host'] = {r['key']: {**(r.get('value') or {}), 'updated_at': r['updated_at']} for r in st}
    except Exception:
        out['host'] = {}
    return out

@app.put('/api/profile')
async def profile_put(req: ProfileRequest, user: dict = Depends(active_user)):
    return await store.save_profile(user, {k: v for k, v in req.model_dump().items() if v is not None})

@app.get('/api/audit')
async def audit_get(user: dict = Depends(active_user)):
    return {'audit': await store.list_audit(user)}

@app.get('/api/dashboard')
async def dashboard_get(user: dict = Depends(active_user)):
    return await store.dashboard_summary(user)

# ---------------- Administração: profissionais + planos ----------------
@app.get('/api/admin/professionals')
async def admin_professionals(user: dict = Depends(active_user)):
    return {'professionals': await store.list_professionals(user)}

@app.post('/api/admin/professionals')
async def admin_professional_create(req: ProfessionalCreate, user: dict = Depends(active_user)):
    return await store.admin_create_professional(user, req.model_dump())

@app.put('/api/admin/plans/{key}')
async def admin_plan_upsert(key: str, req: PlanUpsert, user: dict = Depends(active_user)):
    return await store.upsert_plan(user, key, req.model_dump())

@app.delete('/api/admin/plans/{key}')
async def admin_plan_delete(key: str, user: dict = Depends(active_user)):
    await store.admin_delete_plan(user, key)
    return {'ok': True}

class PasswordRequest(BaseModel):
    password: str

@app.post('/api/admin/professionals/{pid}/password')
async def admin_password(pid: str, req: PasswordRequest, user: dict = Depends(active_user)):
    await store.admin_set_password(user, pid, req.password)
    return {'ok': True}

@app.put('/api/admin/site')
async def admin_site_update(req: dict[str, Any], user: dict = Depends(active_user)):
    return {'site': await store.update_site(user, req)}

class TestResultRequest(BaseModel):
    patient: dict[str,Any]=Field(default_factory=dict)
    patient_id: str|None=None
    test: str
    inputs: dict[str,Any]=Field(default_factory=dict)
    result: dict[str,Any]=Field(default_factory=dict)

@app.get('/api/test-results')
async def test_results_list(user: dict = Depends(active_user)):
    return {'results': await store.list_test_results(user)}

@app.post('/api/test-results')
async def test_results_save(req: TestResultRequest, user: dict = Depends(active_user)):
    return await store.save_test_result(user, req.model_dump())

@app.put('/api/test-results/{rid}')
async def test_results_update(rid: str, req: TestResultRequest, user: dict = Depends(active_user)):
    return await store.save_test_result(user, req.model_dump(), rid)

@app.delete('/api/test-results/{rid}')
async def test_results_delete(rid: str, user: dict = Depends(active_user)):
    await store.delete_test_result(user, rid)
    return {'ok': True}

class VideoRequest(BaseModel):
    title: str|None=None
    test: str|None=None
    url: str|None=None
    description: str|None=None
    sort: int|None=None

@app.get('/api/videos')
async def videos_list(user: dict = Depends(active_user)):
    return {'videos': await store.list_videos(user), 'platform_url': 'https://aluno.serneuropsi.com.br/'}

@app.post('/api/admin/videos')
async def admin_video_create(req: VideoRequest, user: dict = Depends(active_user)):
    return await store.admin_save_video(user, req.model_dump())

@app.put('/api/admin/videos/{vid}')
async def admin_video_update(vid: str, req: VideoRequest, user: dict = Depends(active_user)):
    return await store.admin_save_video(user, req.model_dump(), vid)

@app.delete('/api/admin/videos/{vid}')
async def admin_video_delete(vid: str, user: dict = Depends(active_user)):
    await store.admin_delete_video(user, vid)
    return {'ok': True}

@app.get('/api/qplataforma')
async def qplataforma_list(user: dict = Depends(current_user)):
    return qplataforma.public_list()

# ---------------- Públicas: landing page ----------------
@app.get('/api/site')
async def site_get():
    return {'site': await store.get_site()}

@app.get('/api/public/plans')
async def public_plans():
    plans = await store.list_plans(None) if store.SUPABASE_URL else []
    return {'plans': [p for p in plans if p.get('active')]}

@app.get('/api/plans')
async def plans_list(user: dict = Depends(current_user)):
    return {'plans': await store.list_plans(user)}

@app.put('/api/admin/professionals/{pid}')
async def admin_professional_update(pid: str, req: ProfessionalUpdate, user: dict = Depends(active_user)):
    return await store.admin_update_professional(user, pid, req.model_dump())

@app.delete('/api/admin/professionals/{pid}')
async def admin_professional_delete(pid: str, user: dict = Depends(active_user)):
    await store.admin_delete_professional(user, pid)
    return {'ok': True}

class GrantRequest(BaseModel):
    delta: float

@app.post('/api/admin/professionals/{pid}/credits')
async def admin_grant(pid: str, req: GrantRequest, user: dict = Depends(active_user)):
    return {'balance': await store.admin_grant_credits(user, pid, req.delta)}

# ---------------- Pacientes ----------------
@app.get('/api/patients')
async def patients_list(user: dict = Depends(active_user)):
    return {'patients': await store.list_patients(user)}

@app.post('/api/patients')
async def patients_create(req: PatientRequest, user: dict = Depends(active_user)):
    return await store.save_patient(user, req.model_dump())

@app.put('/api/patients/{pid}')
async def patients_update(pid: str, req: PatientRequest, user: dict = Depends(active_user)):
    return await store.save_patient(user, req.model_dump(), pid)

@app.delete('/api/patients/{pid}')
async def patients_delete(pid: str, user: dict = Depends(active_user)):
    await store.delete_patient(user, pid)
    return {'ok': True}

# ---------------- Créditos e pagamento (Mercado Pago) ----------------
class CheckoutRequest(BaseModel):
    pack: str

@app.get('/api/credits')
async def credits_get(user: dict = Depends(current_user)):
    return {'balance': await store.credit_balance(user),
            'ledger': await store.list_ledger(user),
            'payments_enabled': payments.enabled()}

@app.post('/api/checkout')
async def checkout(req: CheckoutRequest, user: dict = Depends(current_user)):
    if not user.get('anon') and store.access_state(await store.get_profile(user))['blocked'] == 'pending':
        raise HTTPException(403, 'pending: aguarde o administrador liberar o seu acesso antes de comprar créditos.')
    return await store.create_order(user, req.pack)

@app.post('/api/webhooks/mercadopago')
async def mp_webhook(request: Request):
    # MP envia ?type=payment&data.id=... e/ou corpo JSON {type, data:{id}}
    qp = request.query_params
    pid = qp.get('data.id') or qp.get('id')
    kind = qp.get('type') or qp.get('topic')
    if not pid:
        try:
            body = await request.json()
            kind = kind or body.get('type') or body.get('action')
            pid = (body.get('data') or {}).get('id') or body.get('id')
        except Exception:
            pass
    if not pid or (kind and 'payment' not in str(kind)):
        return {'ok': True, 'skip': True}
    try:
        return await store.fulfill_payment(str(pid))
    except HTTPException:
        return {'ok': False}  # 200 p/ o MP não reenfileirar em loop

_MAX_BODY=int(os.getenv('MAX_BODY_MB','120'))*1024*1024
_NOINDEX=('/app','/login.html','/api/')


@app.middleware('http')
async def _hardening(request: Request, call_next):
    """Cabeçalhos de segurança, limite de upload e regras de cache/indexação."""
    path=request.url.path
    cl=request.headers.get('content-length')
    if cl and cl.isdigit() and int(cl) > _MAX_BODY:
        return JSONResponse({'detail': 'Envio grande demais. Divida os arquivos em lotes menores.'}, status_code=413)
    resp = await call_next(request)
    h=resp.headers
    h.setdefault('X-Content-Type-Options', 'nosniff')
    h.setdefault('X-Frame-Options', 'SAMEORIGIN')
    h.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    h.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=(), usb=()')
    h.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    h.setdefault('Cross-Origin-Opener-Policy', 'same-origin-allow-popups')
    if path.startswith(_NOINDEX):
        h.setdefault('X-Robots-Tag', 'noindex, nofollow')
    if path.startswith('/api/') and 'cache-control' not in h:
        h['Cache-Control'] = 'no-store'   # dados clínicos nunca ficam em cache
    # Vídeos: a Cloudflare não repassa pedidos por partes (Range → 206) de conteúdo em cache,
    # e o Safari/iPhone só toca vídeo com 206. 'private' faz a Cloudflare repassar ao servidor.
    if path.startswith('/assets/video/'):
        h['Cache-Control'] = 'private, max-age=3600'
    return resp


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    ref=uuid.uuid4().hex[:8]
    log.exception('Erro não tratado em %s %s [ref %s]', request.method, request.url.path, ref, exc_info=exc)
    return JSONResponse({'detail': f'Erro interno. Se persistir, informe ao suporte o código {ref}.'}, status_code=500)


app.mount('/assets',StaticFiles(directory=STATIC),name='assets')


def _asset_hash(name: str) -> str:
    """Hash curto do conteúdo do asset — muda só quando o arquivo muda."""
    try:
        import hashlib
        return hashlib.md5((STATIC/name).read_bytes()).hexdigest()[:10]
    except OSError:
        return ''


def _index_html() -> Response:
    """index.html com cache-busting nos assets locais (?v=<hash do arquivo>).

    A página em si vai com no-cache (é minúscula e sempre revalida), então cada
    deploy que altere app.js/styles.css entra sozinho — sem refresh manual.
    """
    try:
        html = (STATIC/'index.html').read_text(encoding='utf-8')
    except OSError:
        raise HTTPException(500, 'index.html ausente')
    for asset in ('app.js', 'shell.js', 'laudo.js', 'anamnese.js', 'styles.css'):
        h = _asset_hash(asset)
        if h:
            html = html.replace(f'/assets/{asset}"', f'/assets/{asset}?v={h}"')
    return Response(html, media_type='text/html; charset=utf-8',
                    headers={'Cache-Control': 'no-cache'})


def _page(name: str, status: int = 200) -> Response:
    try:
        html = (STATIC/name).read_text(encoding='utf-8')
    except OSError:
        raise HTTPException(404, 'Página não encontrada')
    return Response(html, status_code=status, media_type='text/html; charset=utf-8',
                    headers={'Cache-Control': 'no-cache'})


def _not_found() -> Response:
    try:
        return _page('404.html', 404)
    except HTTPException:
        return Response('Página não encontrada', status_code=404, media_type='text/plain; charset=utf-8')


# HEAD também (monitores de disponibilidade e pré-visualização de links usam HEAD).
@app.api_route('/', methods=['GET', 'HEAD'])
def landing():
    try:
        return _page('landing.html')
    except HTTPException:
        return _index_html()

@app.api_route('/video', methods=['GET', 'HEAD'])
def video_page():
    return _page('video.html')  # vídeo publicitário (link para compartilhar)

@app.api_route('/page', methods=['GET', 'HEAD'])
@app.api_route('/apresentacao', methods=['GET', 'HEAD'])
def apresentacao():
    return _page('lp.html')  # peça publicitária (link próprio para anúncios)

@app.api_route('/privacidade', methods=['GET', 'HEAD'])
def privacidade():
    return _page('privacidade.html')

@app.api_route('/termos', methods=['GET', 'HEAD'])
def termos():
    return _page('termos.html')

@app.api_route('/app', methods=['GET', 'HEAD'])
def index():
    return _index_html()

@app.get('/robots.txt')
def robots():
    body=('User-agent: *\nAllow: /\nDisallow: /app\nDisallow: /api/\nDisallow: /login.html\n\n'
          f'Sitemap: {PUBLIC_URL}/sitemap.xml\n')
    return Response(body, media_type='text/plain; charset=utf-8', headers={'Cache-Control': 'public, max-age=86400'})

@app.get('/sitemap.xml')
def sitemap():
    today=date.today().isoformat()
    urls=[('/', '1.0'), ('/apresentacao', '0.8'), ('/video', '0.6'), ('/privacidade', '0.3'), ('/termos', '0.3')]
    items=''.join(f'<url><loc>{PUBLIC_URL}{u}</loc><lastmod>{today}</lastmod><priority>{pr}</priority></url>' for u, pr in urls)
    xml=f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</urlset>'
    return Response(xml, media_type='application/xml', headers={'Cache-Control': 'public, max-age=86400'})

@app.get('/favicon.ico')
def favicon():
    return FileResponse(STATIC/'favicon.svg', media_type='image/svg+xml',
                        headers={'Cache-Control': 'public, max-age=604800'})

@app.get('/{path:path}')
def spa(path: str):
    # Rotas de API desconhecidas: 404 em JSON (o fetch do front espera JSON).
    if path == 'api' or path.startswith('api/'):
        raise HTTPException(404, 'Recurso não encontrado')
    # Nunca deixar a rota coringa sair da pasta static (resolve() + relative_to()
    # barram '..', .env, o banco etc.).
    static_root = STATIC.resolve()
    try:
        target = (static_root / path).resolve()
        target.relative_to(static_root)
    except (OSError, ValueError):
        return _not_found()
    if path == 'index.html':
        return _index_html()
    if target.is_file() and target.suffix.lower() not in ('.py', '.sh', '.json', '.md', '.db'):
        return FileResponse(target)
    return _not_found()
