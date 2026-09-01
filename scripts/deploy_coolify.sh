#!/usr/bin/env bash
# ============================================================
# Deploy do NeuroScore no Coolify — rode UMA vez na sua máquina.
#
#   export COOLIFY_TOKEN='8|xxxxxxxx'
#   export OPENAI_API_KEY='sk-...'
#   bash scripts/deploy_coolify.sh
#
# Cria a Application no projeto "Neuropsi SaaS - Dev", define as
# variáveis de ambiente e dispara o primeiro deploy.
#
# Pré-requisito no Coolify: o GitHub App precisa enxergar o repo
# ivoneifs/testes- (privado). Se o repo não for encontrado, conecte
# o GitHub em Coolify -> Sources e rode o script de novo.
# ============================================================
set -euo pipefail

COOLIFY_URL="${COOLIFY_URL:-https://painel.appsbrasil.store}"
API="$COOLIFY_URL/api/v1"
TOKEN="${COOLIFY_TOKEN:?defina COOLIFY_TOKEN}"
PY="${PY:-python}"

PROJECT_UUID="finsyusux15is62bblsg8i19"     # Neuropsi SaaS - Dev
SERVER_UUID="nqxspvxfokp5jjmjamr88ia9"      # localhost
ENVIRONMENT="production"
GITHUB_APP_UUID="pf31tln0b2xv7uck97qhl9is"  # terrible-tamarin
GIT_REPO="ivoneifs/testes-"
GIT_BRANCH="main"
DOMAIN="https://neuro-testes.appsbrasil.store"

OPENAI_API_KEY="${OPENAI_API_KEY:?defina OPENAI_API_KEY}"
OPENAI_MODEL="${OPENAI_MODEL:-gpt-5.6}"
SUPABASE_URL="${SUPABASE_URL:-https://jqmfcqbblrqtmlzpxbud.supabase.co}"
SUPABASE_ANON_KEY="${SUPABASE_ANON_KEY:-sb_publishable_SJHNoCgdokjWlpPM6gQwKQ_qU9Pgjzy}"

AUTH=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")
api() { curl -sS "${AUTH[@]}" "$@"; }
pyget() { "$PY" -c "import sys,json;print(json.load(sys.stdin)$1)"; }

echo "==> Coolify version: $(api "$API/version")"

APP_UUID="$(api "$API/applications" | "$PY" -c \
  "import sys,json;print(next((a['uuid'] for a in json.load(sys.stdin) if a.get('git_repository')=='$GIT_REPO'),''))")"

if [ -n "$APP_UUID" ]; then
  echo "==> Application já existe: $APP_UUID"
else
  echo "==> Criando Application (private-github-app)..."
  RESP="$(api -X POST "$API/applications/private-github-app" -d "$(cat <<JSON
{"project_uuid":"$PROJECT_UUID","server_uuid":"$SERVER_UUID","environment_name":"$ENVIRONMENT",
 "github_app_uuid":"$GITHUB_APP_UUID","git_repository":"$GIT_REPO","git_branch":"$GIT_BRANCH",
 "build_pack":"dockerfile","dockerfile_location":"/Dockerfile","ports_exposes":"8000",
 "name":"neuroscore","description":"NeuroScore",
 "domains":"$DOMAIN","health_check_enabled":true,"health_check_path":"/api/health",
 "instant_deploy":false}
JSON
)")"
  echo "$RESP"
  APP_UUID="$(echo "$RESP" | pyget ".get('uuid','')")" || true
  [ -n "$APP_UUID" ] || { echo "!! Falha ao criar. Veja a mensagem acima (repo não visível ao GitHub App?)."; exit 1; }
  echo "==> Criada: $APP_UUID"
fi

echo "==> Variáveis de ambiente..."
for kv in \
  "OPENAI_API_KEY=$OPENAI_API_KEY" \
  "OPENAI_MODEL=$OPENAI_MODEL" \
  "SUPABASE_URL=$SUPABASE_URL" \
  "SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY" ; do
  k="${kv%%=*}"; v="${kv#*=}"
  body="{\"key\":\"$k\",\"value\":\"$v\",\"is_preview\":false}"
  api -X POST "$API/applications/$APP_UUID/envs" -d "$body" >/dev/null 2>&1 \
    || api -X PATCH "$API/applications/$APP_UUID/envs" -d "$body" >/dev/null 2>&1 \
    || echo "   (aviso: não consegui definir $k via API — defina no painel)"
  echo "   $k ok"
done

echo "==> Deploy..."
api "$API/deploy?uuid=$APP_UUID&force=false"
echo
echo "==> Feito. Acompanhe o build no painel; ao terminar: $DOMAIN"
