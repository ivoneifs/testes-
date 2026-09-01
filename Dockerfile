# NeuroScore — imagem para deploy (Coolify / Docker)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# curl para o healthcheck do Coolify
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Dependências primeiro (cache de camada)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código + dados
COPY . .

# Gera o banco normativo a partir da planilha, se ele não veio no repositório.
# (a planilha OU o .db precisam existir em data/ — ver DEPLOY_COOLIFY.md)
RUN if [ ! -f data/neuro_normas.db ] && [ -f data/Planilha_correcao.xlsx ]; then \
        echo "Gerando data/neuro_normas.db a partir da planilha..." && \
        python -m server.build_db ; \
    fi

# Falha cedo e com mensagem clara se não houver base normativa.
RUN test -f data/neuro_normas.db || \
    (echo "ERRO: data/neuro_normas.db ausente e sem data/Planilha_correcao.xlsx para gerá-lo." && exit 1)

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=6 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/api/health" || exit 1

# Coolify injeta $PORT; mantém 8000 como padrão local.
CMD ["sh", "-c", "python -m uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
