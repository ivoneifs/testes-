from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .workbook_engine import WorkbookEngine
from .openai_service import analyze_anamnesis, generate_integrated_report, generate_test_report

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

@app.post('/api/ai/integrated-report')
def ai_integrated(req: IntegratedRequest):
    try:
        return generate_integrated_report(req.patient,req.anamnesis,req.test_reports,req.raw_results)
    except Exception as exc:
        raise HTTPException(502,str(exc))

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
