"""Q-Plataforma Web (Casa do Psicólogo / Pearson Clinical Brasil).

O NeuroScore NÃO reproduz esses testes: perguntas, normas e correção são da
Pearson. A profissional corrige lá, com os protocolos que comprou, e envia o
relatório (PDF) na Geração de Laudo — os escores vêm prontos e são só
transcritos. Aqui ficam apenas os NOMES dos testes, para a triagem reconhecer
os relatórios e a tela listar o que é suportado.

`nativo` = nome no catálogo do NeuroScore quando o motor também corrige o teste
a partir dos escores brutos (planilhas da própria profissional).
"""
from __future__ import annotations

URL = 'https://cprogerwin0927.websiteseguro.com/casadopsicologo2/testepsi_new/list_testes.asp'

TESTS: list[dict] = [
    {'nome': 'APM - Matrizes Progressivas Avançadas de Raven'},
    {'nome': 'BAYLEY III - Escala Cognitiva'},
    {'nome': 'BAYLEY III - Escala de Linguagem'},
    {'nome': 'BAYLEY III - Escala Motora'},
    {'nome': 'BAYLEY III - Formulário de registro'},
    {'nome': 'BAYLEY III - Questionário Socioemocional e de Comportamento Adaptativo'},
    {'nome': 'BAYLEY III - Teste de Triagem'},
    {'nome': 'BETA-III - Subteste Códigos'},
    {'nome': 'BETA-III - Subteste Raciocínio Matricial'},
    {'nome': 'BFP - Bateria Fatorial de Personalidade', 'nativo': 'BFP'},
    {'nome': 'BPR5 - Bateria de Provas de Raciocínio - RA'},
    {'nome': 'BPR5 - Bateria de Provas de Raciocínio - RE'},
    {'nome': 'BPR5 - Bateria de Provas de Raciocínio - RM'},
    {'nome': 'BPR5 - Bateria de Provas de Raciocínio - RN'},
    {'nome': 'BPR5 - Bateria de Provas de Raciocínio - RV'},
    {'nome': 'CMMS 3 - Escala de Maturidade Mental Colúmbia - Edição Brasileira Revisada'},
    {'nome': 'COLUMBIA - Escala de Maturidade Mental'},
    {'nome': 'CPM - Matrizes Progressivas Coloridas de Raven'},
    {'nome': 'EAE-EP - Escala de Autoeficácia para Escolha Profissional'},
    {'nome': 'EASV - Escala de Atenção Seletiva Visual'},
    {'nome': 'EATA - Escala de Avaliação de Tendências à Agressividade'},
    {'nome': 'EFEx - Escala Fatorial de Extroversão'},
    {'nome': 'EFN - Escala Fatorial de Neuroticismo'},
    {'nome': 'EFS - Escala Fatorial de Socialização'},
    {'nome': 'EMA-EF - Escala de Avaliação da Motivação para Aprender - Ensino Fundamental'},
    {'nome': 'Escala-QVT - Escala de Avaliação da Qualidade de Vida no Trabalho'},
    {'nome': 'ETDAH-II - Escala do Transtorno de Déficit de Atenção/Hiperatividade', 'nativo': 'ETDAH-2'},
    {'nome': 'EVHAD - Escala Vazquez-Hutz de Avaliação de Desempenho'},
    {'nome': 'IFP - Inventário Fatorial de Personalidade'},
    {'nome': 'IFP II - Inventário Fatorial de Personalidade'},
    {'nome': 'IHS - Del Prette - Inventário de Habilidades Sociais'},
    {'nome': 'IHS 2 - Del Prette - Inventário de Habilidades Sociais'},
    {'nome': 'IHSA - Inventário de Habilidades Sociais - Adolescentes'},
    {'nome': 'IHSC - Inventário de Habilidades Sociais Conjugais'},
    {'nome': 'ISSL - Inventário de Sintomas de Stress - Lipp'},
    {'nome': 'LJI - Indicador de Julgamento de Liderança'},
    {'nome': 'MVR - Teste de Memória Visual de Rostos'},
    {'nome': 'MVT - Teste de Memória Visual para o Trânsito'},
    {'nome': 'PFISTER - As Pirâmides Coloridas de Pfister - Adulto', 'nativo': 'Pfister'},
    {'nome': 'PFISTER - As Pirâmides Coloridas de Pfister - Infantil', 'nativo': 'Pfister'},
    {'nome': 'PS2 - Perfil Sensorial 2 - Abreviado', 'nativo': 'Perfil Sensorial 2 - Abreviado'},
    {'nome': 'PS2 - Perfil Sensorial 2 - Acompanhamento Escolar', 'nativo': 'Perfil Sensorial 2 - Professor'},
    {'nome': 'PS2 - Perfil Sensorial 2 - Bebê', 'nativo': 'Perfil Sensorial 2 - Bebê'},
    {'nome': 'PS2 - Perfil Sensorial 2 - Criança', 'nativo': 'Perfil Sensorial 2 - Criança'},
    {'nome': 'PS2 - Perfil Sensorial 2 - Criança Pequena', 'nativo': 'Perfil Sensorial 2 - Criança Pequena'},
    {'nome': 'QSG - Questionário de Saúde Geral de Goldberg'},
    {'nome': 'SDS - Ferramenta de Orientação Vocacional e de Carreira'},
    {'nome': 'SSRS - Inventário de Habilidades Sociais para Crianças'},
    {'nome': 'TCR - Teste Conciso de Raciocínio'},
    {'nome': 'TEACO-FF - Teste de Atenção Concentrada'},
    {'nome': 'TEACO-FF - Teste de Atenção Concentrada - 3ª Edição'},
    {'nome': 'TEADI - Teste de Atenção Dividida'},
    {'nome': 'TEADI - Teste de Atenção Dividida - 2ª Edição'},
    {'nome': 'TEALT - Teste de Atenção Alternada'},
    {'nome': 'TEALT - Teste de Atenção Alternada - 2ª Edição'},
    {'nome': 'TEM-R - Teste de Memória de Reconhecimento'},
    {'nome': 'TIG-NV - Teste de Inteligência Geral - Não Verbal'},
    {'nome': 'TTC - Teste de Trilhas Coloridas'},
    {'nome': 'WAIS-III - Escala de Inteligência Wechsler para Adultos - 3ª Edição', 'nativo': 'WAIS-III'},
    {'nome': 'WASI - Escala Wechsler Abreviada de Inteligência', 'nativo': 'WASI'},
    {'nome': 'WISC-IV - Escala Wechsler de Inteligência para Crianças', 'nativo': 'WISC-IV'},
    {'nome': 'WNV - Escala Wechsler Não Verbal de Inteligência'},
]

NAMES = [t['nome'] for t in TESTS]


def public_list() -> dict:
    return {'url': URL, 'tests': TESTS}


def triage_hint() -> str:
    """Texto extra para a triagem/laudo reconhecerem os relatórios da Q-Plataforma."""
    return ('TESTES DA Q-PLATAFORMA (Pearson / Casa do Psicólogo). Um relatório gerado pela Q-Plataforma '
            '(cabeçalho "Q-Plataforma", "Casa do Psicólogo" ou "Pearson", com escores padronizados, '
            'percentis ou classificações) JÁ VEM CORRIGIDO: situacao = "corrigido", e use em "instrumento" '
            'o nome exato desta lista. Os escores desse relatório prevalecem: não recalcule.\n'
            + '\n'.join(NAMES))
