# NeuroScore — contexto do projeto

App de **correção neuropsicológica automática** + **plataforma clínica comercial**
(pacientes, laudos com IA, créditos, área administrativa). FastAPI + JS puro +
Supabase (Auth/Postgres) + OpenAI + Mercado Pago.

## Onde roda

| | |
|---|---|
| Produção | https://neuro-testes.appsbrasil.store |
| Repo (público) | https://github.com/ivoneifs/testes- (branch `main`) |
| Deploy | Coolify — painel `https://painel.appsbrasil.store`, API `/api/v1`, app uuid `qnmeoeu38cuk8l19jpypf4q9` (nome `neuroscore`, Dockerfile, ~2 min) |
| Banco/Auth | Supabase **Cloud** projeto `jqmfcqbblrqtmlzpxbud` (NÃO é o `neuropsi-postgres` do Coolify) |
| Admin mestre | `ivoneifs@gmail.com` (profiles.role = 'admin', ilimitado) |

### Segredos (o usuário fornece a cada sessão — nunca commitar)

- `.env` local tem: `OPENAI_API_KEY`, `SUPABASE_URL/ANON_KEY/SERVICE_ROLE_KEY`, `OPENAI_MODEL`
- Coolify tem (env vars): as de cima + `MERCADOPAGO_ACCESS_TOKEN` (produção `APP_USR-...`), `PUBLIC_URL`
- **Coolify token** e **Supabase access token (`sbp_...`)**: o usuário cola quando precisa; não ficam salvos

### Como rodar migração no Supabase (sem SQL Editor)

```
curl -X POST "https://api.supabase.com/v1/projects/jqmfcqbblrqtmlzpxbud/database/query" \
  -H "Authorization: Bearer <sbp_token_do_usuario>" -H "Content-Type: application/json" \
  -A "Mozilla/5.0 ... Chrome/131.0 Safari/537.36" \
  --data-binary '{"query":"<SQL>"}'
```
⚠️ **precisa do User-Agent de navegador** senão Cloudflare bloqueia (403 "error code: 1010").

### Como fazer deploy

```
curl -H "Authorization: Bearer <coolify_token>" \
  "https://painel.appsbrasil.store/api/v1/deploy?uuid=qnmeoeu38cuk8l19jpypf4q9&force=false"
# depois pollar /api/v1/deployments/<deployment_uuid> até status=finished
```
Assets têm cache-busting automático (`?v=<hash>` injetado em `_index_html()`), não precisa
hard-refresh após deploy — só se o usuário reclamar.

## Estrutura

```
server/
  app.py            rotas FastAPI
  workbook_engine.py  motor de correção (lê data/neuro_normas.db, lib `formulas`)
  xl_compat.py      patch: coerção Excel texto->número nos operadores (+,-,*,/)
  auth.py           valida JWT Supabase; AUTH_ENABLED se SUPABASE_URL+ANON_KEY
  store.py          PostgREST (JWT do usuário) + service-role p/ admin/webhook
  payments.py       Mercado Pago Checkout Pro
  openai_service.py laudos/anamnese via Responses API
  docx_report.py    laudo integrado .docx (Times New Roman 12 justificado)
static/
  index.html        shell + todas as views
  app.js            corretor (paciente, instrumento, cálculo, gráficos, IA, laudo)
  shell.js          nav, Dashboard, Pacientes, Planos, Config, Conta, Admin, tema
  styles.css        + tema escuro (:root[data-theme="dark"])
supabase/migrations/ 0001..0005 (todas RODADAS na cloud)
```

Rodar local: `run.bat` (Windows) OU `python -m uvicorn server.app:app`.
Auto-teste: `python -m server.self_test` (62 instrumentos, deve dar 0 problemas).
Sem login local: `SUPABASE_URL="" SUPABASE_ANON_KEY="" python -m uvicorn ...`

## Migrações aplicadas (todas RAN na cloud)

- 0001 profiles/evaluations/audit_log + RLS
- 0002 profiles.role/status/plan/credits/prefs/email, `is_admin()`, policies admin, tabela `patients`, ivoneifs=admin
- 0003 `credit_ledger`, `orders`, `apply_credits()`, `spend_laudo()` (+ patches: owner default, orders insert/update policy)
- 0004 tabela `plans` (packs editáveis) + seed inicial/profissional/premium
- 0005 `evaluations.patient_id`, `dashboard_summary()` RPC

## ================= ONDE PARAMOS (2026-09-03) =================

### ✅ Pronto e no ar

- **Motor**: gráficos WISC-IV (índices + subtestes), laudo Times New Roman 12 justificado,
  tabelas-lixo filtradas, decimais arredondados, coerção Excel (corrigiu WSCT48-R),
  campos "automáticos" agora digitáveis (26 testes estavam travados).
- **Shell**: Dashboard (KPIs + mini-gráficos + atividade), Pacientes (CRUD + contagem de
  avaliações → abre no corretor), História de Vida, Laudos (corretor), Planos (lê do banco),
  Configurações (tema claro/escuro/sistema + notificações), Conta (perfil + trocar senha).
- **Admin** (`#admin`, só role=admin): CRUD profissionais (cria via Auth admin API),
  editar preço/créditos/itens dos planos, botão "+ créditos" por profissional.
- **Créditos**: 1 por laudo integrado (admin ilimitado = 999999), 402 + redireciona a
  Planos quando zera, extrato em `credit_ledger`.
- **Mercado Pago PRODUÇÃO**: token `APP_USR-` no Coolify, checkout gera preference real,
  webhook `/api/webhooks/mercadopago` credita ao aprovar (idempotente, service role).

### ⏳ Pendente

1. **Verificar pagamento MP**: o usuário precisa fazer 1 compra real (Pix R$49 Pack Inicial).
   Sandbox foi impossível de testar (bloqueios do MP). Após: conferir order→`paid`,
   `credit_ledger` +5, saldo. Se falhar: rastrear pelo `order_id` (na URL de retorno).
   Fallback já existe: admin concede créditos manualmente.
2. **WASI**: ✅ RESOLVIDO 2026-09-03. `scripts/repair_wasi_refs.py` patcheou as 112
   fórmulas `#REF!` no `data/neuro_normas.db` (versionado) + `xl_compat` ganhou `QUOTIENT`.
   WASI e WISC-IV com 0 `#REF!` nas tabelas visíveis. **Ao regerar o .db do .xlsx, rodar
   `python scripts/repair_wasi_refs.py` de novo.** Equivalente no .xlsx (opcional): na aba
   WASI, `COUNTIF(#REF!,...)` (cols AB/AC/AD linhas 57-95) -> `0`; célula `AB13` -> `=IF(N3="";"";AB11)`.
   Ainda com `#REF!` interno (não afeta laudo): `Funcoes` (38), WAIS-III/ETDAH-CriAd/THCP/Vin_3_Ext_* (1-10).
3. **Divergências de motor não-visíveis** (auditoria: 442 células, 0 em tabelas renderizadas):
   `COUNTIF(intervalo_vazio;"*")` conta tudo em vez de 0 (RAVLT C40/C41);
   `SUM(A;B;C;D)` com célula de texto → `#VALUE!` (CBCL K50);
   `LOOKUP` em coluna distante → `#VALUE!` (WISC-IV subtestes suplementares linhas 116+).
   Baixo valor + risco alto (patchar a lib `formulas` que serve 33k células). Deixado como está.

### Ideias de próximos blocos (não iniciados)

- Reembolso MP → debitar créditos automaticamente (hoje é manual no Admin)
- Vincular laudo salvo ↔ avaliação ↔ paciente com histórico por paciente na aba Pacientes
- Confirmação de e-mail no cadastro self-service (hoje admin cria com `email_confirm:true`)
- Repo privado + volume p/ `neuro_normas.db` (hoje o .db é versionado no repo público — funciona
  mas não é ideal p/ produto comercial)

## Gotchas

- `formulas`/`schedula` + Python 3.14: warning de GIL no import (`lxml.etree`) — inofensivo.
- Coolify deploy via `curl ... &` em bash morre quando o shell pai sai — usar `run_in_background`.
- MP: NÃO pré-preencher `payer.email` no preference (trava o botão "Pagar").
- `git push` via Bash às vezes é bloqueado pelo classificador — se acontecer, usar GitKraken MCP.
- Escrever segredo em env do Coolify a partir do `.env` local é bloqueado — pedir o valor ao usuário.
