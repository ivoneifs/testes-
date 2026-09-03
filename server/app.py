from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Carrega o .env ANTES de importar módulos locais que leem env no import (auth).
ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')

from .workbook_engine import WorkbookEngine
from .openai_service import (analyze_anamnesis, analyze_laudo_model, extract_external_instrument,
                             generate_integrated_report, generate_test_report)
from .docx_report import build_integrated_docx
from . import auth, payments, store, scales
from .auth import current_user

STATIC=ROOT/'static'
DB=ROOT/'data'/'neuro_normas.db'

app=FastAPI(title='Correção Neuropsicológica Automática',version='1.0.0')
engine=WorkbookEngine(DB)

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
    credits: int|None=None

class ProfessionalCreate(BaseModel):
    email: str
    password: str
    full_name: str|None=None
    professional_id: str|None=None
    role: str|None='professional'
    credits: int|None=0

class PlanUpsert(BaseModel):
    name: str|None=None
    credits: int|None=None
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
def tests(user: dict = Depends(current_user)):
    return {'tests':engine.catalog() + scales.catalog_entries()}

@app.get('/api/tests/{test_name}')
def test_meta(test_name: str, user: dict = Depends(current_user)):
    name=unquote(test_name)
    if scales.is_scale(name):
        return scales.meta(name)
    try:
        return engine.test_meta(name)
    except KeyError:
        raise HTTPException(404,'Teste não encontrado')
    except Exception as exc:
        raise HTTPException(500,f'Falha ao preparar o teste: {type(exc).__name__}: {exc}')

@app.post('/api/score')
def score(req: ScoreRequest, user: dict = Depends(current_user)):
    if scales.is_scale(req.test):
        return scales.score(req.test,req.patient,req.raw_scores,req.parameters)
    try:
        return engine.score(req.test,req.patient,req.raw_scores,req.parameters)
    except KeyError as exc:
        raise HTTPException(404,str(exc))
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    except Exception as exc:
        raise HTTPException(500,f'Erro de correção: {type(exc).__name__}: {exc}')

@app.post('/api/ai/test-report')
def ai_test_report(req: TestReportRequest, user: dict = Depends(current_user)):
    try:
        return generate_test_report(req.patient,req.score_result,req.history)
    except Exception as exc:
        raise HTTPException(502,str(exc))

@app.post('/api/ai/anamnesis')
async def ai_anamnesis(patient_json: str=Form('{}'), files: list[UploadFile]=File(...),
                       user: dict = Depends(current_user)):
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
        if mime!='application/pdf' and not mime.startswith('image/'):
            raise HTTPException(415,f'{f.filename}: envie PDF ou imagem')
        parsed.append((f.filename or 'arquivo',mime,data))
    if total>45*1024*1024:
        raise HTTPException(413,'Total de anexos acima de 45 MB')
    try:
        return analyze_anamnesis(parsed,patient)
    except Exception as exc:
        raise HTTPException(502,str(exc))

@app.post('/api/ai/laudo-model')
async def ai_laudo_model(files: list[UploadFile]=File(...), user: dict = Depends(current_user)):
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
                                 user: dict = Depends(current_user)):
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
async def ai_integrated(req: IntegratedRequest, user: dict = Depends(current_user)):
    if auth.AUTH_ENABLED and not await store.can_laudo(user):
        raise HTTPException(402, 'Créditos insuficientes. Compre um pacote em Planos para gerar o laudo.')
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

@app.post('/api/laudo/integrated-docx')
def laudo_integrated_docx(req: IntegratedDocxRequest, user: dict = Depends(current_user)):
    if not req.report:
        raise HTTPException(400,'Gere o laudo integrado antes de exportar.')
    try:
        data=build_integrated_docx(req.patient,req.report,req.tests,req.charts)
    except Exception as exc:
        raise HTTPException(500,f'Falha ao gerar o .docx: {type(exc).__name__}: {exc}')
    name=f"avaliacao_neuropsicologica_completa_{_slug(req.patient.get('name',''))}_{date.today().isoformat()}.docx"
    return Response(
        content=data,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={'Content-Disposition': f'attachment; filename=\"{name}\"'},
    )

# ---------------- Avaliações salvas (Supabase) ----------------
@app.get('/api/evaluations')
async def evaluations_list(patient: str | None = None, user: dict = Depends(current_user)):
    return {'evaluations': await store.list_evaluations(user, patient)}

@app.get('/api/evaluations/{eval_id}')
async def evaluations_get(eval_id: str, user: dict = Depends(current_user)):
    return await store.get_evaluation(user, eval_id)

@app.post('/api/evaluations')
async def evaluations_create(req: EvaluationRequest, user: dict = Depends(current_user)):
    return await store.save_evaluation(user, req.model_dump())

@app.put('/api/evaluations/{eval_id}')
async def evaluations_update(eval_id: str, req: EvaluationRequest, user: dict = Depends(current_user)):
    return await store.save_evaluation(user, req.model_dump(), eval_id)

@app.delete('/api/evaluations/{eval_id}')
async def evaluations_delete(eval_id: str, user: dict = Depends(current_user)):
    await store.delete_evaluation(user, eval_id)
    return {'ok': True}

@app.get('/api/profile')
async def profile_get(user: dict = Depends(current_user)):
    return await store.get_profile(user)

@app.put('/api/profile')
async def profile_put(req: ProfileRequest, user: dict = Depends(current_user)):
    return await store.save_profile(user, {k: v for k, v in req.model_dump().items() if v is not None})

@app.get('/api/audit')
async def audit_get(user: dict = Depends(current_user)):
    return {'audit': await store.list_audit(user)}

@app.get('/api/dashboard')
async def dashboard_get(user: dict = Depends(current_user)):
    return await store.dashboard_summary(user)

# ---------------- Administração: profissionais + planos ----------------
@app.get('/api/admin/professionals')
async def admin_professionals(user: dict = Depends(current_user)):
    return {'professionals': await store.list_professionals(user)}

@app.post('/api/admin/professionals')
async def admin_professional_create(req: ProfessionalCreate, user: dict = Depends(current_user)):
    return await store.admin_create_professional(user, req.model_dump())

@app.put('/api/admin/plans/{key}')
async def admin_plan_upsert(key: str, req: PlanUpsert, user: dict = Depends(current_user)):
    return await store.upsert_plan(user, key, req.model_dump())

@app.get('/api/plans')
async def plans_list(user: dict = Depends(current_user)):
    return {'plans': await store.list_plans(user)}

@app.put('/api/admin/professionals/{pid}')
async def admin_professional_update(pid: str, req: ProfessionalUpdate, user: dict = Depends(current_user)):
    return await store.admin_update_professional(user, pid, req.model_dump())

@app.delete('/api/admin/professionals/{pid}')
async def admin_professional_delete(pid: str, user: dict = Depends(current_user)):
    await store.admin_delete_professional(user, pid)
    return {'ok': True}

class GrantRequest(BaseModel):
    delta: int

@app.post('/api/admin/professionals/{pid}/credits')
async def admin_grant(pid: str, req: GrantRequest, user: dict = Depends(current_user)):
    return {'balance': await store.admin_grant_credits(user, pid, req.delta)}

# ---------------- Pacientes ----------------
@app.get('/api/patients')
async def patients_list(user: dict = Depends(current_user)):
    return {'patients': await store.list_patients(user)}

@app.post('/api/patients')
async def patients_create(req: PatientRequest, user: dict = Depends(current_user)):
    return await store.save_patient(user, req.model_dump())

@app.put('/api/patients/{pid}')
async def patients_update(pid: str, req: PatientRequest, user: dict = Depends(current_user)):
    return await store.save_patient(user, req.model_dump(), pid)

@app.delete('/api/patients/{pid}')
async def patients_delete(pid: str, user: dict = Depends(current_user)):
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
    for asset in ('app.js', 'shell.js', 'styles.css'):
        h = _asset_hash(asset)
        if h:
            html = html.replace(f'/assets/{asset}"', f'/assets/{asset}?v={h}"')
    return Response(html, media_type='text/html; charset=utf-8',
                    headers={'Cache-Control': 'no-cache'})


@app.get('/')
def index():
    return _index_html()

@app.get('/{path:path}')
def spa(path: str):
    # Unknown API routes must 404 as JSON, not silently fall back to index.html
    # (which would make the frontend fetch helper choke on an HTML body).
    if path == 'api' or path.startswith('api/'):
        raise HTTPException(404, 'Recurso não encontrado')
    # Never allow the catch-all SPA route to escape the static directory.
    # Path.resolve() normalizes '..' segments; relative_to() then rejects any
    # resolved path outside STATIC (including files such as .env and the DB).
    static_root = STATIC.resolve()
    try:
        target = (static_root / path).resolve()
        target.relative_to(static_root)
    except (OSError, ValueError):
        return _index_html()
    if target.is_file():
        return FileResponse(target)
    return _index_html()
