from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .workbook_engine import WorkbookEngine
from .openai_service import analyze_anamnesis, analyze_laudo_model, generate_integrated_report, generate_test_report
from .docx_report import build_integrated_docx

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
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
    model: dict[str,Any]|None=None

class IntegratedDocxRequest(BaseModel):
    patient: dict[str,Any]=Field(default_factory=dict)
    report: dict[str,Any]
    tests: list[str]=Field(default_factory=list)


def _slug(text: str) -> str:
    text=unicodedata.normalize('NFKD',text or '').encode('ascii','ignore').decode()
    text=re.sub(r'[^A-Za-z0-9]+','_',text).strip('_').lower()
    return text or 'paciente'

@app.get('/api/health')
def health():
    return {'ok':True,'tests':len(engine.list_tests()),'openai_configured':bool(os.getenv('OPENAI_API_KEY'))}

@app.get('/api/tests')
def tests():
    return {'tests':engine.catalog()}

@app.get('/api/tests/{test_name}')
def test_meta(test_name: str):
    try:
        return engine.test_meta(unquote(test_name))
    except KeyError:
        raise HTTPException(404,'Teste não encontrado')
    except Exception as exc:
        raise HTTPException(500,f'Falha ao preparar o teste: {type(exc).__name__}: {exc}')

@app.post('/api/score')
def score(req: ScoreRequest):
    try:
        return engine.score(req.test,req.patient,req.raw_scores,req.parameters)
    except KeyError as exc:
        raise HTTPException(404,str(exc))
    except Exception as exc:
        raise HTTPException(500,f'Erro de correção: {type(exc).__name__}: {exc}')

@app.post('/api/ai/test-report')
def ai_test_report(req: TestReportRequest):
    try:
        return generate_test_report(req.patient,req.score_result,req.history)
    except Exception as exc:
        raise HTTPException(502,str(exc))

@app.post('/api/ai/anamnesis')
async def ai_anamnesis(patient_json: str=Form('{}'), files: list[UploadFile]=File(...)):
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
async def ai_laudo_model(files: list[UploadFile]=File(...)):
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

@app.post('/api/ai/integrated-report')
def ai_integrated(req: IntegratedRequest):
    try:
        return generate_integrated_report(req.patient,req.anamnesis,req.test_reports,req.raw_results,req.model)
    except Exception as exc:
        raise HTTPException(502,str(exc))

@app.post('/api/laudo/integrated-docx')
def laudo_integrated_docx(req: IntegratedDocxRequest):
    if not req.report:
        raise HTTPException(400,'Gere o laudo integrado antes de exportar.')
    try:
        data=build_integrated_docx(req.patient,req.report,req.tests)
    except Exception as exc:
        raise HTTPException(500,f'Falha ao gerar o .docx: {type(exc).__name__}: {exc}')
    name=f"laudo_{_slug(req.patient.get('name',''))}_{date.today().isoformat()}.docx"
    return Response(
        content=data,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={'Content-Disposition': f'attachment; filename=\"{name}\"'},
    )

app.mount('/assets',StaticFiles(directory=STATIC),name='assets')

@app.get('/')
def index():
    return FileResponse(STATIC/'index.html')

@app.get('/{path:path}')
def spa(path: str):
    target=STATIC/path
    if target.exists() and target.is_file():
        return FileResponse(target)
    return FileResponse(STATIC/'index.html')
