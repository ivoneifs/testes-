# Deploy no Coolify — NeuroScore

Alvo: `https://neuro-testes.appsbrasil.store` (DNS já aponta para Cloudflare).

## 1. Base normativa (obrigatória)

O motor de correção precisa de `data/neuro_normas.db` (gerado da planilha).
Ele **não** está no repositório público. Escolha uma:

- **A. Repositório privado** (recomendado): torne o repo privado e faça commit de
  `data/neuro_normas.db` (68 MB, ok para repo privado). O Dockerfile usa direto.
- **B. Volume persistente**: no Coolify, crie um volume montado em `/app/data` e
  suba o arquivo `neuro_normas.db` para ele uma vez.
- **C. Planilha no repo privado**: faça commit de `data/Planilha_correcao.xlsx`;
  o Dockerfile roda `python -m server.build_db` no build.

## 2. Aplicação no Coolify

- **Tipo**: Application → do repositório GitHub `ivoneifs/testes-`
- **Build pack**: Dockerfile
- **Porta**: `8000`
- **Domínio**: `neuro-testes.appsbrasil.store` (Coolify emite o certificado)
- **Health check**: `GET /api/health`

## 3. Variáveis de ambiente (Coolify → Environment Variables)

```
OPENAI_API_KEY=...            # sua chave
OPENAI_MODEL=gpt-5.6
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_ANON_KEY=...         # chave anon/public
SUPABASE_JWT_AUD=authenticated
# opcional, só se o backend precisar de escrita privilegiada:
# SUPABASE_SERVICE_ROLE_KEY=...
```

Nunca faça commit desses valores — só no painel do Coolify.

## 4. Banco de dados dos usuários

Auth + dados no **Supabase** (Postgres + RLS). As tabelas e políticas ficam em
`supabase/migrations/` (a ser criado). Não é necessário MongoDB.
