from __future__ import annotations

import base64
import json
import os
from typing import Any

import httpx

OPENAI_URL = 'https://api.openai.com/v1/responses'

TEST_REPORT_SCHEMA = {
    'type': 'object',
    'properties': {
        'teste': {'type': 'string'},
        'sintese_quantitativa': {'type': 'string'},
        'interpretacao': {'type': 'string'},
        'pontos_fortes': {'type': 'array', 'items': {'type': 'string'}},
        'fragilidades': {'type': 'array', 'items': {'type': 'string'}},
        'integracao_clinica': {'type': 'string'},
        'limitacoes': {'type': 'array', 'items': {'type': 'string'}},
        'texto_para_laudo': {'type': 'string'},
    },
    'required': ['teste','sintese_quantitativa','interpretacao','pontos_fortes','fragilidades','integracao_clinica','limitacoes','texto_para_laudo'],
    'additionalProperties': False,
}

ANAMNESIS_SCHEMA = {
    'type': 'object',
    'properties': {
        'resumo': {'type': 'string'},
        'historia_de_vida': {'type': 'string'},
        'secoes': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'titulo': {'type': 'string'},
                    'conteudo': {'type': 'string'},
                    'evidencias': {'type': 'array', 'items': {'type': 'string'}},
                },
                'required': ['titulo','conteudo','evidencias'],
                'additionalProperties': False,
            },
        },
        'linha_do_tempo': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'periodo': {'type': 'string'},
                    'evento': {'type': 'string'},
                    'fonte': {'type': 'string'},
                },
                'required': ['periodo','evento','fonte'],
                'additionalProperties': False,
            },
        },
        'lacunas': {'type': 'array', 'items': {'type': 'string'}},
        'observacoes_legibilidade': {'type': 'array', 'items': {'type': 'string'}},
    },
    'required': ['resumo','historia_de_vida','secoes','linha_do_tempo','lacunas','observacoes_legibilidade'],
    'additionalProperties': False,
}

INTEGRATED_SCHEMA = {
    'type': 'object',
    'properties': {
        'identificacao_e_demanda': {'type': 'string'},
        'historia_clinica_e_desenvolvimental': {'type': 'string'},
        'procedimentos_e_instrumentos': {'type': 'string'},
        'resultados_por_dominio': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'dominio': {'type': 'string'},
                    'descricao': {'type': 'string'},
                    'evidencias': {'type': 'array', 'items': {'type': 'string'}},
                },
                'required': ['dominio','descricao','evidencias'],
                'additionalProperties': False,
            },
        },
        'integracao_neuropsicologica': {'type': 'string'},
        'hipoteses_e_diferenciais': {'type': 'array', 'items': {'type': 'string'}},
        'recomendacoes': {'type': 'array', 'items': {'type': 'string'}},
        'limitacoes': {'type': 'array', 'items': {'type': 'string'}},
        'conclusao': {'type': 'string'},
    },
    'required': ['identificacao_e_demanda','historia_clinica_e_desenvolvimental','procedimentos_e_instrumentos','resultados_por_dominio','integracao_neuropsicologica','hipoteses_e_diferenciais','recomendacoes','limitacoes','conclusao'],
    'additionalProperties': False,
}


def _api_key():
    key=os.getenv('OPENAI_API_KEY','').strip()
    if not key:
        raise RuntimeError('OPENAI_API_KEY não configurada no servidor.')
    return key


def _model():
    return os.getenv('OPENAI_MODEL','gpt-5.6').strip() or 'gpt-5.6'


def _extract_output_text(data: dict) -> str:
    # The REST response exposes output items; output_text is an SDK convenience property.
    parts=[]
    for item in data.get('output',[]):
        if item.get('type')!='message':
            continue
        for content in item.get('content',[]):
            if content.get('type') in ('output_text','text') and content.get('text'):
                parts.append(content['text'])
    if not parts and isinstance(data.get('output_text'),str):
        return data['output_text']
    return '\n'.join(parts)


def _request(input_items: list[dict], schema_name: str, schema: dict, instructions: str):
    payload={
        'model': _model(),
        'store': False,
        'instructions': instructions,
        'input': input_items,
        'text': {
            'format': {
                'type': 'json_schema',
                'name': schema_name,
                'strict': True,
                'schema': schema,
            }
        },
    }
    with httpx.Client(timeout=120.0) as client:
        resp=client.post(
            OPENAI_URL,
            headers={'Authorization':f'Bearer {_api_key()}','Content-Type':'application/json'},
            json=payload,
        )
    if resp.status_code>=400:
        detail=resp.text[:2000]
        raise RuntimeError(f'OpenAI API retornou HTTP {resp.status_code}: {detail}')
    data=resp.json()
    text=_extract_output_text(data)
    if not text:
        raise RuntimeError('A OpenAI API não retornou texto estruturado.')
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError('Resposta estruturada inválida recebida da OpenAI API.') from exc


def generate_test_report(patient: dict, score_result: dict, history: dict | None = None):
    safe_payload={
        'patient': patient,
        'test_result': score_result,
        'history_summary': history or {},
    }
    instructions=(
        'Atue como assistente de redação neuropsicológica para um profissional habilitado. '
        'Use exclusivamente os dados fornecidos. Não invente sintomas, histórico, escores, percentis ou diagnósticos. '
        'Separe resultado quantitativo de interpretação clínica. Quando os dados forem insuficientes, declare a limitação. '
        'Não conclua diagnóstico apenas por um teste isolado. Produza linguagem técnica, clara, humanizada e revisável.'
    )
    return _request(
        [{'role':'user','content':[{'type':'input_text','text':json.dumps(safe_payload,ensure_ascii=False,default=str)}]}],
        'test_report',TEST_REPORT_SCHEMA,instructions
    )


def analyze_anamnesis(files: list[tuple[str,str,bytes]], patient: dict):
    content=[{
        'type':'input_text',
        'text':(
            'Leia os documentos de anamnese anexados e organize a história de vida do paciente. '
            'Preserve fatos, datas e incertezas. Se a escrita manuscrita estiver ilegível, indique isso em observacoes_legibilidade. '
            'Quando algo não estiver informado, registre como lacuna em vez de inferir.'
            '\nDados cadastrais disponíveis: '+json.dumps(patient,ensure_ascii=False,default=str)
        )
    }]
    for filename,mime,data in files:
        b64=base64.b64encode(data).decode('ascii')
        if mime=='application/pdf' or filename.lower().endswith('.pdf'):
            content.append({
                'type':'input_file',
                'filename':filename,
                'file_data':f'data:application/pdf;base64,{b64}',
            })
        elif mime.startswith('image/'):
            content.append({
                'type':'input_image',
                'image_url':f'data:{mime};base64,{b64}',
                'detail':'auto',
            })
        else:
            raise ValueError(f'Formato não suportado: {filename} ({mime})')
    instructions=(
        'Atue como assistente de organização de anamnese neuropsicológica. '
        'Extraia somente informações presentes nos documentos e nos dados cadastrais fornecidos. '
        'Não crie diagnóstico, não preencha lacunas por suposição e não transforme hipótese do informante em fato confirmado. '
        'Organize cronologicamente quando possível e produza uma história de vida clínica coesa para revisão profissional.'
    )
    return _request([{'role':'user','content':content}], 'anamnesis_history', ANAMNESIS_SCHEMA, instructions)


LAUDO_MODEL_SCHEMA = {
    'type': 'object',
    'properties': {
        'titulo_sugerido': {'type': 'string'},
        'secoes': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'titulo': {'type': 'string'},
                    'conteudo_esperado': {'type': 'string'},
                },
                'required': ['titulo', 'conteudo_esperado'],
                'additionalProperties': False,
            },
        },
        'estilo_de_escrita': {'type': 'string'},
        'observacoes_de_formatacao': {'type': 'array', 'items': {'type': 'string'}},
    },
    'required': ['titulo_sugerido', 'secoes', 'estilo_de_escrita', 'observacoes_de_formatacao'],
    'additionalProperties': False,
}


def analyze_laudo_model(files: list[tuple[str, str, bytes]]):
    content = [{
        'type': 'input_text',
        'text': (
            'Analise o(s) documento(s) de MODELO de laudo neuropsicológico anexado(s). '
            'Extraia apenas a ESTRUTURA e a FORMATAÇÃO: títulos de seção, ordem das seções, '
            'que tipo de conteúdo cada seção espera, o estilo de escrita (tom, pessoa, tempo verbal, '
            'nível de formalidade) e convenções de formatação (uso de tópicos, tabelas, negrito, etc.). '
            'NÃO extraia dados clínicos, nomes ou resultados do paciente do modelo — só o formato.'
        )
    }]
    for filename, mime, data in files:
        b64 = base64.b64encode(data).decode('ascii')
        if mime == 'application/pdf' or filename.lower().endswith('.pdf'):
            content.append({'type': 'input_file', 'filename': filename,
                            'file_data': f'data:application/pdf;base64,{b64}'})
        elif mime.startswith('image/'):
            content.append({'type': 'input_image', 'image_url': f'data:{mime};base64,{b64}', 'detail': 'auto'})
        elif mime.startswith('text/') or filename.lower().endswith(('.txt', '.md')):
            content.append({'type': 'input_text', 'text': data.decode('utf-8', 'replace')[:20000]})
        else:
            content.append({'type': 'input_file', 'filename': filename,
                            'file_data': f'data:{mime or "application/octet-stream"};base64,{b64}'})
    instructions = (
        'Você mapeia o formato de modelos de laudo. Responda somente sobre estrutura, estilo e '
        'formatação — nunca sobre o conteúdo clínico de exemplo contido no modelo.'
    )
    return _request([{'role': 'user', 'content': content}], 'laudo_model', LAUDO_MODEL_SCHEMA, instructions)


def generate_integrated_report(patient: dict, anamnesis: dict | None, test_reports: list[dict],
                               raw_results: list[dict], model: dict | None = None):
    payload={
        'patient':patient,
        'anamnesis':anamnesis or {},
        'test_reports':test_reports,
        'quantitative_results':raw_results,
    }
    instructions=(
        'Atue como assistente de redação de laudo neuropsicológico para revisão de profissional habilitado. '
        'Integre história e resultados sem inventar informações. Diferencie achado objetivo, interpretação, hipótese e recomendação. '
        'Hipóteses diagnósticas devem ser condicionais e nunca baseadas em um único escore. '
        'Inclua limitações e divergências entre fontes. O texto final deve ser estruturado, técnico e legível.'
    )
    if model:
        payload['modelo_de_formatacao']=model
        instructions+=(
            ' Foi fornecido um MODELO DE FORMATAÇÃO em "modelo_de_formatacao": siga a estrutura, a ordem '
            'das seções, os títulos, o estilo de escrita e as convenções de formatação desse modelo o '
            'máximo possível dentro do formato de saída exigido. Distribua o conteúdo pelas seções do '
            'esquema de forma que reflita as seções do modelo. Não copie nenhum dado clínico do modelo.'
        )
    return _request(
        [{'role':'user','content':[{'type':'input_text','text':json.dumps(payload,ensure_ascii=False,default=str)}]}],
        'integrated_neuropsychological_report', INTEGRATED_SCHEMA, instructions
    )
