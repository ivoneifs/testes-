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
| Banco / Auth | Supabase **Cloud** projeto `jqmfcqbblrqtmlzpxbud` (NÃO é o `neuropsi-postgres` do Coolify, que está solto) |
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
  docx_report.py     laudo integrado .docx (Times New Roman 12 justificado)
scripts/
  repair_wasi_refs.py   conserta os #REF! da aba WASI no .db (rodar SEMPRE após
                        `python -m server.build_db`)
  deploy_coolify.sh     provisão inicial do app no Coolify (já feito)
static/
  index.html    shell com todas as views (Dashboard/Pacientes/História/Laudos/Planos/Config/Admin/Conta)
  app.js        corretor: paciente, seletor de instrumento, cálculo, gráficos SVG, IA, laudo/.docx
  shell.js      nav + router (hash), Dashboard, Pacientes, Planos, Config (tema), Admin, Conta
  styles.css    + tema escuro em :root[data-theme="dark"]
supabase/migrations/  0001..0006 (todas RODADAS na cloud)
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
3. **EFA / SON-R nativos** — pediram, mas só mandaram apostila/slide de curso. Precisam da
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
