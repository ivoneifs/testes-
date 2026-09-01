# NeuroScore — Correção Neuropsicológica Automática

Aplicação web local construída a partir da planilha de correção fornecida. O objetivo é permitir **digitar os pontos brutos** e recalcular automaticamente os resultados segundo as fórmulas e tabelas normativas existentes no arquivo original, incluindo seleção por idade e outros parâmetros que a própria planilha utiliza.

## Recursos

- 62 módulos clínicos/testes detectados na base original.
- Modo **Somente PB** quando a planilha possui totais/subescalas brutas que alimentam diretamente a norma.
- Datas de nascimento e aplicação alimentam automaticamente a faixa etária da fórmula.
- Sexo, escolaridade e parâmetros adicionais são utilizados quando a planilha original os exige.
- Resultados normativos, percentis, classificações, escores padronizados e índices seguem as fórmulas da base Excel.
- Gráficos responsivos por família de instrumento:
  - WISC/WAIS/WASI: perfil de subtestes/índices;
  - RAVLT/HVLT/BVMT: curva de aprendizagem;
  - FDT/Stroop/Hayling/Trilhas/Wisconsin: perfil executivo;
  - Vineland/SRS/BRIEF/ETDAH: domínios/escalas;
  - testes acadêmicos: perfil de desempenho.
- Impressão pelo navegador / salvar como PDF.
- Exportação da sessão em JSON.
- OpenAI API no backend para:
  - laudo estruturado de cada teste;
  - upload de anamnese em PDF ou imagem;
  - leitura de fotografia/escaneamento manuscrito;
  - organização da história de vida;
  - laudo neuropsicológico integrado para revisão profissional.

## Windows — iniciar

1. Tenha **Python 3.11+** instalado com o comando `py` disponível.
2. Dê duplo clique em **`run.bat`**.
3. Na primeira execução o sistema cria `.venv`, instala as dependências e abre `http://127.0.0.1:8000`.

A correção dos testes funciona sem internet. A internet só é necessária para instalar dependências na primeira execução e para as funções da OpenAI.

## Configurar a OpenAI

1. Copie `.env.example` para `.env` (o `run.bat` faz isso automaticamente se o arquivo ainda não existir).
2. Abra `.env` e preencha:

```text
OPENAI_API_KEY=sua_chave_aqui
OPENAI_MODEL=gpt-5.6
```

3. Reinicie o servidor.

**Nunca** coloque a chave no `index.html` ou em `app.js`. Ela deve permanecer somente no backend/arquivo `.env`.

As requisições de IA usam a Responses API com saída estruturada por JSON Schema. O código envia `store=false`. PDFs e imagens só são enviados quando a pessoa clica explicitamente no botão de análise da anamnese.

## Fluxo de uso

1. Preencha paciente, nascimento, aplicação, sexo e escolaridade.
2. Escolha o instrumento na lateral.
3. Digite apenas os pontos brutos apresentados.
4. Clique em **Calcular resultados**.
5. Confira tabelas e gráficos.
6. Se a OpenAI estiver configurada, clique em **Gerar laudo deste teste**.
7. Na anamnese, carregue PDF/JPG/PNG e clique em **Analisar e gerar história**.
8. Depois de calcular os testes desejados, use **Gerar laudo integrado**.

## Validação

Execute `self_test.bat`. O auto-teste percorre o catálogo e executa verificações de cadeia de cálculo, incluindo WISC-IV e RAVLT em modo de pontos brutos.

## Observações clínicas importantes

Este software é uma ferramenta de apoio à correção e redação. A IA não deve substituir julgamento profissional, análise qualitativa, observação comportamental ou integração clínica. O texto gerado pela API deve ser revisado por profissional habilitado antes de integrar qualquer documento clínico.

A fidelidade normativa depende das fórmulas/tabelas contidas na planilha de origem. Se uma norma, versão ou instrumento for atualizado, a base também deve ser atualizada e validada.
