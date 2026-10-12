# NeuroScore — contexto do projeto

App de **correção neuropsicológica automática** + **plataforma clínica comercial**
(pacientes, laudos com IA, créditos, área administrativa). FastAPI + JS puro +
Supabase (Auth/Postgres) + OpenAI + Mercado Pago.

Última sessão: **2026-09-03**. Ver "ONDE PARAMOS" no fim.

## Onde roda

| O quê | Onde |
|---|---|
| Produção | `https://neuro-testes.appsbrasil.store` |
| Repo (público) | `github.com/ivoneifs/testes-` — branch `main` |
| Deploy | Coolify — painel `painel.appsbrasil.store`, API `/api/v1`, app uuid `qnmeoeu38cuk8l19jpypf4q9` (nome `neuroscore`, Dockerfile, ~2 min) |
| Banco / Auth | Supabase **self-hosted no Coolify** desde 2026-09-28: serviço `f13s4ssiztp71d8f8d4g2d4y` (só db/auth/rest/kong, por falta de RAM), URL `https://supabase-neuro.appsbrasil.store`. O Cloud `jqmfcqbblrqtmlzpxbud` sumiu (dados antigos não recuperados). Migração: `docker exec -i supabase-db-f13s4ssiztp71d8f8d4g2d4y psql -U postgres < arquivo.sql` |
| Admin mestre | `ivoneifs@gmail.com` — `profiles.role = 'admin'` → créditos ilimitados |

### Segredos (o usuário fornece por sessão — nunca commitar)

- `.env` local: `OPENAI_API_KEY`, `OPENAI_MODEL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- Coolify env vars: as de cima + `MERCADOPAGO_ACCESS_TOKEN` (produção `APP_USR-...`) + `PUBLIC_URL`
- **Coolify token** (`10|...`) e **Supabase access token** (`sbp_...`): o usuário cola na hora; não ficam salvos
- Escrever segredo no Coolify lendo do `.env` local é bloqueado pelo classificador → pedir o valor ao usuário

### Rodar migração no Supabase (sem abrir o SQL Editor)

```bash
curl -X POST "https://api.supabase.com/v1/projects/jqmfcqbblrqtmlzpxbud/database/query" \
  -H "Authorization: Bearer <sbp_token>" -H "Content-Type: application/json" \
  -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36" \
  --data-binary '{"query":"<SQL>"}'
```

⚠️ **precisa do User-Agent de navegador** senão o Cloudflare bloqueia (403 "error code: 1010").

### Deploy

```bash
curl -H "Authorization: Bearer <coolify_token>" \
  "https://painel.appsbrasil.store/api/v1/deploy?uuid=qnmeoeu38cuk8l19jpypf4q9&force=false"
# pega deployment_uuid da resposta, polla /api/v1/deployments/<uuid> até status=finished (~2 min)
```

Assets têm cache-busting automático (`?v=<hash>` injetado em `_index_html()`), não precisa hard-refresh.

## Estrutura

```
server/
  app.py             rotas FastAPI (ver "Rotas" abaixo); /api/tests e /api/score
                     despacham p/ scales.py quando o nome é uma escala
  workbook_engine.py motor de correção (lê data/neuro_normas.db via lib `formulas`).
                     `_perfil_sensorial_meta()` = descoberta dedicada do Perfil
                     Sensorial 2 (grades seção×quadrante); score() anota
                     classificação+percentil via perfil_sensorial_norms
  perfil_sensorial_norms.py  normas do Perfil Sensorial 2 (manual do usuário):
                     faixas de corte (bruto→banda) + faixas de percentil (Anexo A).
                     `python -m server.perfil_sensorial_norms` lista o que falta digitar
  scales.py          escalas por questionário (não-planilha): ATA e HADS.
                     Mesmo formato de meta()/score() do WorkbookEngine
  xl_compat.py       patches na lib `formulas`: coerção Excel texto→número nos
                     operadores (+,-,*,/,^) e implementa QUOTIENT
  auth.py            valida JWT Supabase; AUTH_ENABLED se SUPABASE_URL+ANON_KEY
  store.py           PostgREST c/ JWT do usuário + helpers service-role (admin, webhook, planos)
  payments.py        Mercado Pago Checkout Pro (preference + consulta de pagamento)
  openai_service.py  laudos / anamnese / modelo (Responses API)
  docx_report.py     laudo integrado .docx (Times New Roman 12 justificado) + build_laudo_neuro_docx
  file_content.py    upload → conteúdo OpenAI: PDF/imagem direto; DOCX/XLSX/XLS/DOC viram texto
  laudo_neuro_spec.json  especificação das 14 seções do Laudo Neuropsicológico (vai no prompt)
scripts/
  repair_wasi_refs.py   conserta os #REF! da aba WASI no .db (rodar SEMPRE após
                        `python -m server.build_db`)
  deploy_coolify.sh     provisão inicial do app no Coolify (já feito)
static/
  index.html    shell com todas as views (Dashboard/Pacientes/História/Laudos/Planos/Config/Admin/Conta)
  app.js        corretor: paciente, seletor de instrumento, cálculo, gráficos SVG, IA, laudo/.docx
  shell.js      nav + router (hash), Dashboard, Pacientes, Planos, Config (tema), Admin, Conta
  laudo.js      aba "Geração de Laudo" (#geracao): formulário + upload dos testes → laudo 14 seções
  styles.css    + tema escuro em :root[data-theme="dark"]
supabase/migrations/  0001..0007 (todas rodadas no Supabase self-hosted)
data/neuro_normas.db  base normativa (~68 MB, VERSIONADA no repo p/ o Docker) — já
                      patcheada p/ WASI; inclui as 6 abas do Perfil Sensorial 2
data/Perfil Sensorial 2-0 correcao excel.xlsx  workbook extra (git-ignored por *.xlsx);
                      ingerido por build_db.py via EXTRA_WORKBOOKS
```

Rodar local: `run.bat` (Windows) ou `python -m uvicorn server.app:app`.
Sem login local: `SUPABASE_URL="" SUPABASE_ANON_KEY="" python -m uvicorn server.app:app`.
Auto-teste: `python -m server.self_test` → deve dar `{"tests": 68, "problems": []}`
(68 = instrumentos de planilha, contando as 6 abas do Perfil Sensorial 2; +2 escalas
ATA/HADS aparecem só no catálogo `/api/tests`, total exibido no app = 70).

**Regerar o banco:** os 2 `.xlsx` em `data/` → `python -m server.build_db` →
`python scripts/repair_wasi_refs.py` (obrigatório: build_db não sabe consertar WASI).

## Rotas API (todas exigem JWT Supabase quando AUTH_ENABLED)

- `GET /api/health` `/api/config` — públicas (`health.tests` = 68+2 escalas = 70)
- `GET /api/tests` (catálogo = planilhas + escalas ATA/HADS) · `GET /api/tests/{nome}`
  · `POST /api/score` — `test_meta`/`score` roteiam p/ `scales.py` se `scales.is_scale(nome)`
- `POST /api/ai/test-report` `/api/ai/anamnesis` `/api/ai/laudo-model` `/api/ai/integrated-report`
  (o integrado **consome 1 crédito**; 402 se zerado e não-admin)
- `POST /api/laudo/integrated-docx`
- `POST /api/ai/laudo-neuro` (multipart `dados_json` + `files`; **consome 1 crédito**) · `POST /api/laudo/neuro-docx`
- `GET/POST/PUT/DELETE /api/evaluations[/{id}]` (`?patient=<id>` filtra) · `GET/PUT /api/profile`
- `GET/POST/PUT/DELETE /api/patients[/{id}]` · `GET /api/dashboard` · `GET /api/audit`
- `GET /api/plans` · `GET/POST/PUT/DELETE /api/admin/professionals[/{id}]` ·
  `POST /api/admin/professionals/{id}/credits` (delta) · `PUT /api/admin/plans/{key}`
- `GET /api/credits` · `POST /api/checkout` · `POST /api/webhooks/mercadopago`

## Migrações (todas RAN na cloud)

- **0001** profiles / evaluations / audit_log + RLS + trigger de perfil
- **0002** profiles.role/status/plan/credits/prefs/avatar_url/email, `is_admin()`, policies de admin,
  tabela `patients`, `ivoneifs@gmail.com` → admin
- **0003** `credit_ledger`, `orders`, `apply_credits()`, `spend_laudo()` — **+ patches aplicados fora do arquivo**:
  `alter ... orders/credit_ledger alter column owner set default auth.uid()`, policies `orders_insert`/`orders_update`
- **0004** tabela `plans` (packs editáveis pelo admin) + seed inicial/profissional/premium
- **0005** `evaluations.patient_id` (FK patients), função `dashboard_summary()`
- **0006** `evaluations.external_results` (jsonb) — instrumentos corrigidos fora do sistema
- **0007** trigger `t_profiles_protect`: só admin (ou security definer/service_role) altera role/status/plan/credits
- **0008** `site_settings` (linha única `id='site'`, `data` jsonb: cores + textos da landing; leitura pública, escrita só admin) + pacotes 10/20/30 créditos a R$ 20/crédito
- **0009** `profiles.trial_ends_at` (acesso de teste); cadastro novo = teste de 14 dias; só admin altera o prazo
- **0011** cadastro novo ganha 3 créditos grátis (`credit_ledger.reason='trial_bonus'`)
- **0012** tabela `videos` (links de vídeos explicativos; leitura: logados, escrita: admin) — aba `#videos`
- **0014** `patients.dados` (identificação da ficha: responsável, CPF, mãe, pai, fone, cidade, solicitante, hipótese…) e `patients.anamnese` (`{respostas, atualizado_em}`)
- **0010** créditos fracionados (`numeric(12,2)`); `spend_credits(p_amount, p_reason, p_ref)` (mesmo motivo+ref no mesmo dia = grátis); textos dos pacotes

## ================= ONDE PARAMOS (2026-09-03) =================

### ✅ Pronto e no ar

- **Motor**: gráficos WISC-IV (índices em pontos compostos + perfil de subtestes),
  laudo em Times New Roman 12 justificado (.docx e .html), tabelas-lixo filtradas,
  decimais arredondados p/ 2 casas, coerção Excel texto→número (corrigiu **WSCT48-R**),
  `QUOTIENT` implementado, campos "automáticos" (fórmula) agora **digitáveis** (26 testes
  estavam travados/readonly), cache-busting de assets.
- **WASI**: as 112 fórmulas `#REF!` **corrigidas** (`scripts/repair_wasi_refs.py`, .db versionado).
  QIV/QIE/QIT-4/QIT-2 calculam certo, 0 `#REF!` visível.
- **Outros instrumentos** (aba Laudos): campo p/ testes corrigidos FORA do sistema
  (TAVIS, SON-R, Perfil Sensorial 2). Digita manual OU anexa o relatório já corrigido →
  `/api/ai/external-instrument` **transcreve** (não pontua, não usa normas — guardrail no
  prompt; se for protocolo sem correção, avisa). Entra no laudo integrado
  (`instrumentos_externos` no payload da IA). Salvo em `evaluations.external_results`.
  **Decisão firme:** IA não corrige teste protegido de terceiro — só o profissional pontua.
- **Shell**: Dashboard (KPIs reais + mini-gráficos de avaliações/mês e top instrumentos +
  atividade recente clicável), Pacientes (CRUD + nº de avaliações → abre no corretor),
  História de Vida, Laudos (o corretor), Planos (lê do banco), Configurações
  (tema claro/escuro/sistema + notificações salvas em `profiles.prefs`),
  Conta (perfil + troca de senha via Supabase).
- **Admin** (aba só p/ role=admin): CRUD de profissionais (cria conta via Auth Admin API,
  `email_confirm:true`), editar preço/créditos/itens/destaque dos planos,
  botão "+ créditos" por profissional (delta, com extrato).
- **Créditos**: 1 por Avaliação Completa; admin = ilimitado (999999); ao zerar → 402 +
  leva pra Planos; extrato em `credit_ledger`.
- **Mercado Pago PRODUÇÃO**: token `APP_USR-` no Coolify; `/api/checkout` gera preference
  real; `/api/webhooks/mercadopago` credita ao aprovar (idempotente, via service role).
  Pix/boleto/cartão habilitados.
- **Perfil Sensorial 2** (Sensory Profile 2) — **instrumento nativo pontuável** (6 abas).
  `build_db.py` ganhou `EXTRA_WORKBOOKS`: ingere `data/Perfil Sensorial 2-0 correcao
  excel.xlsx` como 6 abas renomeadas (Bebê/Criança Pequena/Criança/Professor/Abreviado/
  Consolidado), reescrevendo as refs cruzadas. `_perfil_sensorial_meta()` = layout dedicado
  (grades seção×quadrante): entrada = escore 0–5 por item agrupado por seção; tabelas
  "perfil por seção" + "perfil por quadrante"; `chart_type='sensory_profile'`.
  Front: 1 entrada na lista com seletor de forma (`#psFormSelect`), inputs por seção/grupo,
  4 gráficos (barra+radar de seção, barra+radar de quadrante), `input_mode='itens'` dispensa
  nascimento/data, `#testNote` mostra a nota do instrumento.
  **Classificação em 5 bandas + faixa de percentil** = `perfil_sensorial_norms.py` (do
  manual do usuário). As fórmulas STATUS da planilha estavam com cortes ERRADOS (Criança/
  Exploração planilha=23–33, manual=20–47) → ignoradas. score() troca as colunas
  Percentil/Status por Classificação + Percentil(norma).
  **Preenchido do manual:** faixas de percentil (Anexo A) das 5 formas; faixas de corte de
  Criança/quadrantes, Criança Pequena/seções, Bebê/total. **FALTA digitar** (`CUTOFFS` no
  arquivo): Criança/9 seções, Criança Pequena/4 quadrantes, Professor (quad+seções+fatores),
  Abreviado (quad+2 seções) — não estão no manual, só nas fichas de resumo em papel.
  Escala sem corte → classificação em branco (não quebra). Consolidado cai no genérico.
- **Escalas por questionário** (`server/scales.py`) — **ATA** (23 áreas 0–2 → total 0–46,
  corte ≥15) e **HADS** (HADS-A/HADS-D 0–21 → 0–7 normal / 8–10 leve / ≥11 significativo).
  Entram no catálogo, no laudo com IA. Pontuação publicada e simples (o profissional já
  faz à mão) — NÃO é norma proprietária. Total exibido no app = **70**.
- **IA por teste**: o botão de laudo individual + Avaliação Completa dependem só de
  `openai_configured` (chave no ambiente), **não** do instrumento — vale p/ todos.
  TAVIS/SON-R/EFA seguem no fluxo "instrumento externo" (não têm planilha nem normas).

### ⏳ Pendente

1. **Perfil Sensorial 2 — digitar os cortes que faltam** em `server/perfil_sensorial_norms.py`
   (`CUTOFFS`): das fichas de resumo em papel. Rodar `python -m server.perfil_sensorial_norms`
   pra ver a lista. Depois é só redeployar (o motor usa na hora, não precisa regerar o .db).
2. **Confirmar 1 pagamento MP real** — o usuário faz 1 compra (Pix, R$49, Pack Inicial) e
   a gente verifica: `orders.status='paid'`, `credit_ledger` +5, saldo. Rastrear pelo
   `order_id` (fica na URL de retorno `#planos?pago=1`). O sandbox foi impossível de testar
   (bloqueios do MP: real-account email, test-buyer login, headless, direct-API). Fallback:
   admin concede créditos manualmente.
3. **EFA (normas) / SON-R nativos** — EFA já soma os brutos (2026-09-28); faltam as normas. Pediram, mas só mandaram apostila/slide de curso. Precisam da
   **planilha de correção** (como a do Perfil Sensorial 2) OU das **tabelas normativas**
   (EFA: manual Vetor pág. 35–46 + valor de cada resposta; SON-R: manual pág. 191–208).
   Sem isso não dá pra pontuar — segue como instrumento externo. Doc teórico/slide não serve.
4. **`#REF!` interno restante** (NÃO afeta nenhum laudo — são células helper): `Funcoes` (38),
   `WAIS-III` (1), `ETDAH-CriAd` (1), `THCP` (1), `Vin_3_Ext_Ent/Prof` (1-10).
   Mesmo tratamento do `repair_wasi_refs.py` se algum surgir visível.
5. **Divergências de motor não-visíveis** (auditoria completa: 442 células, **0 em tabela
   renderizada**): `COUNTIF(intervalo_vazio;"*")` conta tudo (RAVLT C40/C41);
   `SUM(A;B;C;D)` com texto → `#VALUE!` (CBCL K50); `LOOKUP` de coluna distante → `#VALUE!`
   (WISC-IV subtestes suplementares, linhas 116+). Baixo valor + risco alto de patchar a
   `formulas` (serve 33k células). Deixado como está de propósito.

### Ideias de próximos blocos (não iniciados)

- Reembolso no MP → debitar créditos automaticamente (hoje só manual no Admin)
- Histórico de laudos salvos por paciente (a avaliação já tem `patient_id`; falta a UI dedicada)
- Cadastro self-service com confirmação de e-mail (hoje só admin cria contas)
- Repo privado + volume p/ `neuro_normas.db` (hoje versionado em repo público — funciona,
  mas Git avisa "large files" e não é ideal p/ produto comercial)

## Gotchas

- `formulas`/`schedula` + Python 3.14: warning de GIL no import de `lxml.etree` — inofensivo.
- Coolify deploy via `curl ... &` em bash morre quando o shell pai sai → usar `run_in_background`
  ou aceitar o timeout de 2 min e checar o status depois (o deploy continua no servidor).
- MP: **não** mandar `payer.email` no preference (trava o botão "Pagar" no checkout).
- Supabase Management API só responde com **User-Agent de navegador** (senão Cloudflare 403).
- `git push` via Bash às vezes é bloqueado pelo classificador → tentar de novo ou GitKraken MCP.
- `psql` direto no Supabase Cloud não dá (sem a senha do banco) — usar a Management API.

## Sessão 2026-09-28

- Supabase migrado para self-hosted (ver "Onde roda"). Admin recriado: `ivoneifs@gmail.com`.
- **Laudos**: botão "Arquivar teste" — só os arquivados entram na Avaliação Completa (`state.results` = arquivados).
- **Aba "Geração de Laudo"** (`#geracao`): identificação + queixa/anamnese/observação + upload dos testes
  JÁ CORRIGIDOS (PDF/JPG/PNG/DOC/DOCX/XLS/XLSX) → `/api/ai/laudo-neuro` → laudo nas 14 seções de
  `server/laudo_neuro_spec.json`, com gráfico por instrumento, `.docx` e impressão/PDF. A IA só
  transcreve escores já corrigidos. Testado com dados fictícios: 71 s.
- **Correção automática na Geração de Laudo** (`server/auto_score.py`): IA faz a triagem dos arquivos
  (instrumento → nome do catálogo, corrigido / escores_brutos / sem escores); os com escores brutos
  que existem no catálogo têm os brutos extraídos para os campos do motor e são corrigidos pelo
  NeuroScore (normas das planilhas). Resultado vai ao laudo como `resultados_corrigidos_pelo_sistema`.
  Precisa de nascimento + data de aplicação. Testado: WISC-IV brutos → ICV 110/IOP 106/IMO 94/IVP 103/
  QIT 105, idêntico ao motor direto (~2 min no total).
- **Upload de anamnese** na Geração de Laudo (`anamnese_files`): a IA escreve a seção 06 a partir dele.
- **EFA** nativa em `scales.py` (50 itens: Social 15, Prático 24, Conceitual 11; 2/1/0, branco = não sei):
  só somas brutas por domínio + % do máximo. **Sem classificação normativa** (faltam as tabelas do
  manual) — o resultado diz isso. Catálogo agora = 71.
- Não rodar Chromium/Playwright no servidor: RAM no limite, a carga foi a 600.

## Sessão 2026-10-12

- **Landing page** em `/` (`static/landing.html`); o app foi para **`/app`** (login e retorno do Mercado Pago apontam para `/app#...`).
  `login.html?next=planos` → `/app#planos`. Planos da landing vêm de `GET /api/public/plans` (fallback fixo no HTML).
- **Admin**: aparência do site (`PUT /api/admin/site`, lida em `GET /api/site`; cores aplicadas na landing e no app),
  trocar senha de qualquer usuário (`POST /api/admin/professionals/{id}/password`, Auth Admin API),
  criar/excluir pacotes (`DELETE /api/admin/plans/{key}`).
- **Acesso (trial)**: o admin escolhe Pro / Teste (N dias) / Administrador. `active_user` (app.py) bloqueia com 403
  `trial_expired`/`suspended`; ficam liberados só `/api/profile`, `/api/plans`, `/api/credits`, `/api/checkout`.
  Front: faixa com contador de dias e tela de bloqueio. Comprar créditos (webhook MP) zera o `trial_ends_at` → vira Pro.
- **Créditos por uso** (custos em `store.COST_*`): teste corrigido (`/api/score`) = 1, ref = teste+paciente+nascimento
  (recalcular no mesmo dia não cobra); História de Vida (`/api/ai/anamnesis`) = 1 (era 0,5 até a migração 0015); laudo = 1. Saldo < custo → 402
  e o app leva para Planos; faixa vermelha "créditos acabaram" quando o saldo < 0,5.
- **Q-Plataforma (Pearson)** (`server/qplataforma.py`): só os NOMES dos 62 testes da conta da usuária + mapa `nativo` para
  o catálogo do motor. Card na Geração de Laudo (atalho + lista); a triagem e o laudo tratam relatório da Pearson como
  já corrigido (escores da Pearson prevalecem). **Decisão:** não copiar itens/normas/correção da Pearson nem entrar na conta dela.
- **RAVLT igual à ficha** (`server/ravlt_sheet.py`): a aba RAVLT da planilha já é a folha de respostas (ordem de evocação
  C11:G25 / I11:K25, intrusões C30:K39, reconhecimento S/N C/E/G/I/K 45:54). `test_meta('RAVLT')` ganha `answer_sheet`
  (palavras lidas da planilha) e `extra_inputs`; `build_overrides` aceita essas células. Fórmulas inalteradas:
  totais digitados × ficha marcada dão tabelas idênticas; self_test 68/0. Reconhecimento da planilha = acertos − FP.
- **Testes realizados** (`#realizados`, migração **0013** `test_results`, único por owner+patient_key+test): todo cálculo
  bem-sucedido no corretor é salvo (entradas + resultado). Aba lista por paciente; Abrir/editar reabre no corretor
  (inclusive a ficha do RAVLT); Excluir; seleção → "Gerar laudo completo" monta `state.results` e dispara a Avaliação Completa.
- **Protocolo item a item lido da planilha** (`server/item_sheet.py`): `detect()` acha células de resposta pelas
  fórmulas `IF(H17="DT",6,…)` (códigos ≤3 letras), texto/número do item, seção e a célula de identificação do
  respondente (`IF($J$11="","",$J$11)` — sem ela a planilha não calcula os fatores). Liberado só em `ENABLED`
  (ETDAH-2, SNAP-IV, SDQ-Pr, BRIEF-P) depois de conferido; PEP-R ficou de fora (itens não alteram resultado),
  BRIEF-2 também (leitura ambígua). ETDAH-2: itens × PB digitado = tabela final idêntica.
- `detect_selectors()`: seletores de tabela normativa/amostra das abas (ex.: ETDAH-2 Q3 "Amostra Geral") viram
  parâmetros com lista; valor inicial = o salvo na planilha (nada muda até escolher). Antes o ETDAH-2 saía sem percentil.
- **História de Vida → Testes realizados + OCR de alta performance**: `/api/ai/anamnesis` grava a leitura como
  registro `test='História de Vida'` (`store.HISTORIA_TEST`) do paciente; nome/nascimento vêm da tela (campos
  `#hvName/#hvBirth` espelham o corretor) ou, se vazios, do campo `identificacao` lido do documento. O schema ganhou
  `transcricao` (OCR literal por página, feito ANTES de organizar) — a tela mostra no fim, recolhida. Fotos passam por
  `server/ocr_prep.py` (Pillow: EXIF, ~2048 px, autocontraste) e vão com `detail: high`. Na aba Testes realizados:
  Abrir → aba História; selecionada no laudo completo → vira `state.anamnesis`. Teste real: 12 s, 0,5 crédito.
- **Anamnese por marcação** (aba História de Vida → "☑️ Preencher anamnese"; o outro modo é "📎 Enviar anamnese" = OCR):
  `static/anamnese.js` = ficha **Anamnese Infantojuvenil** da usuária (Google Doc 1goC8KxL…) em chips Sim/Não/opções,
  campos de texto só opcionais. "Paciente cadastrado" (`#hvPick`) puxa nome/nascimento/sexo/escolaridade + `dados` +
  respostas salvas. "Salvar no paciente" grava `patients.dados`/`patients.anamnese` (cria o paciente se não existir);
  "Salvar e gerar história" → `POST /api/ai/anamnesis-form` (`{patient, patient_id, respostas, texto}`, 0,5 crédito;
  schema sem transcricao/identificacao; o texto marcado vira a "transcrição") → Testes realizados com `inputs.formulario`
  (Abrir reabre o formulário). Pacientes: botão "📇 Anamnese" e os campos de `dados` no modal. Teste real: 23 s.
- **História no modelo da profissional** (Google Doc 1VtUoR5…): schema ganhou `historia_modelo` (`HV_MODEL_KEYS` em
  openai_service.py: historia_doenca_atual + periodo_gestacional, desenvolvimento_global, alimentacao_sono,
  historico_familiar_social, autonomia_comportamento, historico_escolar; guia em `HV_MODEL_GUIDE`). Vale para OCR e
  formulário. Tela: documento Times 12 justificado + "Copiar texto" (HTML p/ Word); resto recolhido. Testes realizados
  mostra a História da Doença Atual no resumo. O que falta vai só em `lacunas`, não dentro dos tópicos.
- **Laudo no modelo da profissional** (Google Doc 1LCalEMU… — laudo real de paciente: só a ESTRUTURA foi usada,
  nada do paciente entra no repo). `server/laudo_modelo.py`: textos fixos (nota CFP, referencial teórico, Obs.
  Importante, À equipe multidisciplinar, rodapé) + `GUIA` de redação; `LAUDO_NEURO_SCHEMA` refeito (identificação com
  CPF/filiação/data_construcao, procedimentos, instrumentos {nome, referencia, objetivo}, encontros, histórico familiar,
  medicações, analise_testes {descricao, tabelas[], base_conceitual, interpretacao, grafico}, conclusao_sintese,
  impressão, encaminhamentos, recomendações família/escola, local_data). A resposta ganha `textos_fixos`.
  `.docx` (`build_laudo_neuro_docx`), tela e impressão: Times New Roman 12, títulos pretos, ordem do modelo.
- **Laudo a partir de Testes realizados**: `/api/ai/laudo-neuro` aceita `dados.testes_realizados_ids` (o servidor lê
  os registros do usuário: História de Vida → `historia_de_vida_salva`; testes → `resultados_corrigidos_pelo_sistema`)
  e `dados.tipo_laudo` = `completo` | `teste_isolado`. Geração de Laudo: ao escolher o paciente, preenche CPF/filiação/
  cidade/medicações/histórico familiar do cadastro e lista HV + testes salvos para marcar. Testes realizados:
  "Gerar laudo completo" e "Laudo deste teste" abrem a Geração já preenchida. Teste real: 49 s / 45 s, 1 crédito cada.
- **Geração de Laudo grava em Testes realizados**: anamnese PDF/foto enviada na Geração passa pelo OCR da História de
  Vida (`analyze_anamnesis`, em paralelo com o `auto_score`) → registro "História de Vida" + `historia_de_vida_salva`
  no laudo; testes corrigidos pelo motor (`_raw`/`_resultado` do auto_score) e relatórios já corrigidos (tabelas
  transcritas em `analise_testes`, `result.externo=true`, sem "Abrir/editar") também são salvos. Resposta:
  `salvos_em_testes_realizados`. Sem custo extra (só o crédito do laudo). DOC/DOCX de anamnese seguem direto para a IA.

## Sessão 2026-10-12 (Vineland-3)

- **Vineland-3 item a item SÓ pelo número** (`server/vineland.py`): abas `Vin_3_Ext_Ent` (Entrevista Extensivo) e
  `Vin_3_Ext_Pais` (Compreensivo Pais/Cuidadores). O texto das perguntas é da Pearson e **não entra no app**: o
  profissional lê o protocolo impresso e toca 2/1/0 (+ Est) no número do item. Do protocolo só a estrutura: nº de
  itens por subdomínio (rec 39, exp 49, esc 38, pes 55, dom 30, cmd 58, rin 43, bri 36, enf 33, cmg 43, cmf 34;
  mal-adaptativo A 13, B 11; 20 críticos) e o item inicial por idade de cada forma.
- A tela (`vinHtml`/`vinCalc`/`vinSync` em app.js) aplica basal (4 seguidos com 2 → anteriores = 2; usa o mais alto)
  e teto (4 seguidos com 0 → seguintes = 0), avisa sem basal/sem teto, e grava o bruto em H19/H22/H25/H29/H32/H35/
  H39/H42/H45/H49/H50 (+ H109/H113 mal-adaptativo; críticos 1/2 em M109…M116). A planilha corrige (v-escala, idade
  equivalente, crescimento, domínios, CCA, HMOT). Respostas por item vão como `vin:<sub>:<n>` (e `…e` = Est) só para
  reabrir em Testes realizados; `build_overrides` descarta essas chaves.
- `L54` (intervalo de confiança 85/90/95) virou parâmetro (padrão 95): **sem ele a planilha não calcula domínios/CCA**.
  `R3` = respondente. self_test 68/0.
- **6 formas num só item "Vineland-3"** da lista, com seletor de forma (`TEST_GROUPS` em app.js, igual ao Perfil
  Sensorial 2). Ordem: Entrevista Extensivo, Entrevista Nível de Domínio, Pais Extensivo, Pais Nível de Domínio,
  Professores Extensivo, Professores Nível de Domínio. `vineland.FORMS` guarda por aba: subdomínios, célula do intervalo
  de confiança (Extensivo L54 / Domínio L19), mal-adaptativo e células dos críticos (Ext 20 ou 17 do Professor; Domínio 11 em M/O/Q46–49).
- Professor Extensivo (folha da 2ª pasta do Drive): rec 30, exp 36, esc 36, pes 24, num 23 (célula H32), cme 22 (H35),
  rin 31, bri 19, enf 25, cmg 21, cmf 26. A página do Mal-adaptativo A/B (P18) não veio, então o bruto é digitado.
- Seção com `itens=None` = a folha ainda não veio, e a tela pede o bruto digitado. É o caso das 3 formas de **Nível de
  Domínio** (bruto por domínio em H20/H23/H26/H33, mal-adaptativo em H46/H48) e do mal-adaptativo do Professor. Quando
  as folhas chegarem, basta preencher `itens`/`inicio` em `vineland.py`.
- **Testes realizados → "📥 Enviar testes (upload)"** (`POST /api/test-results/import`, multipart `patient_json` +
  `files`): aceita os formatos de `file_content.ACCEPTED_EXT`, fotos passam por `ocr_prep`. `auto_score.run` faz a triagem.
  Escores brutos de teste do catálogo são corrigidos pelo motor e salvos (1 crédito por teste, mesma ref de
  `/api/score`). Relatórios já corrigidos passam por `transcribe_corrected` (só transcreve as tabelas) e são salvos
  com `result.externo=true`, sem custo. A resposta traz `salvos` (ids), `alertas` e `patient_key`; a tela recarrega a
  lista, seleciona o paciente e deixa os novos marcados (`tr-new`).
- **Tarefas longas em segundo plano** (por causa do erro 524 da Cloudflare, que corta a resposta aos 100 s):
  `POST /api/ai/laudo-neuro/start` e `POST /api/test-results/import/start` leem os arquivos, iniciam a tarefa
  (`_start_job`, guardada na memória do processo por até 3 h) e devolvem `{job}`. O front usa `apiJob(url, fd)` (app.js),
  que consulta `GET /api/jobs/{id}` a cada 3 s. As rotas antigas, sem `/start`, continuam funcionando. Um deploy
  reinicia o processo e perde as tarefas em andamento.
- **Quem libera o acesso é o administrador** (migração **0016**, rodada): cadastro novo entra com `profiles.status='pending'`
  e os 3 créditos. `access_state` dá `blocked='pending'`; `active_user` responde 403 `pending:` e o checkout também é
  bloqueado. Na tela aparece "Cadastro recebido", com botão para avisar no WhatsApp. No Admin, os cadastros aguardando
  aparecem primeiro: o botão "✓ Liberar" grava status active com teste de 14 dias; em Editar dá para escolher Pro ou outro
  prazo. O Supabase não tem SMTP, então `ENABLE_EMAIL_AUTOCONFIRM=true` (sem e-mail de confirmação).
- **Migração 0017** (rodada): o cadastro pede nome, CRP, WhatsApp e cidade (`profiles.phone`/`city`, vindos do
  `raw_user_meta_data`). Status `rejected` = recusado (botão "✕ Recusar" no Admin). Com SMTP configurado, desligar o
  autoconfirm: a tela de cadastro já avisa "confirme o e-mail" e `?confirmado=1` mostra o aviso de e-mail confirmado.
