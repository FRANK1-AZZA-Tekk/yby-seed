#!/usr/bin/env bash
# Bootstrap YBY SEED em Ubuntu local (GTX 1650 / docker compose + Ollama).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PATH="${HOME}/.local/bin:${PATH}"

echo "== YBY SEED bootstrap (raiz: $ROOT) =="

mkdir -p ./data/postgres ./data/datasets ./data/models

if [[ ! -f .env ]] && [[ -f .env.example ]]; then
  cp .env.example .env
  echo "[ok] .env criado a partir de .env.example"
elif [[ -f .env ]]; then
  echo "[ok] .env já existe"
else
  echo "[warn] .env.example ausente; configure variáveis manualmente"
fi

if command -v systemctl >/dev/null 2>&1; then
  OVERRIDE_DIR="/etc/systemd/system/ollama.service.d"
  OVERRIDE_FILE="${OVERRIDE_DIR}/yby-host.conf"
  WANT_HOST='Environment="OLLAMA_HOST=0.0.0.0:11434"'
  if systemctl list-unit-files 2>/dev/null | grep -q '^ollama.service'; then
    if [[ -f "$OVERRIDE_FILE" ]] && grep -qF 'OLLAMA_HOST=0.0.0.0:11434' "$OVERRIDE_FILE" 2>/dev/null; then
      echo "[ok] override Ollama OLLAMA_HOST já presente"
    elif [[ ! -d "$OVERRIDE_DIR" ]] || [[ ! -f "$OVERRIDE_FILE" ]]; then
      echo "[info] para expor Ollama na LAN, crie (com sudo) $OVERRIDE_FILE com:"
      echo "       $WANT_HOST"
      echo "       e execute: sudo systemctl daemon-reload && sudo systemctl restart ollama"
    else
      echo "[skip] override Ollama existente em $OVERRIDE_DIR — não sobrescrever"
    fi
  else
    echo "[skip] ollama.service não instalado via systemd"
  fi
else
  echo "[skip] systemctl indisponível"
fi

if command -v ollama >/dev/null 2>&1; then
  pull_if_missing() {
    local model="$1"
    if ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -qxF "$model"; then
      echo "[ok] modelo $model já presente"
    else
      echo "[pull] ollama pull $model"
      ollama pull "$model" || echo "[warn] pull $model falhou"
    fi
  }
  pull_if_missing "qwen2.5-coder:7b-instruct-q4_K_M"
  pull_if_missing "nomic-embed-text"
else
  echo "[warn] ollama não encontrado — pule pull de modelos; instale em https://ollama.com"
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose up -d
  echo "[wait] healthchecks postgres, redis, litellm..."
  deadline=$((SECONDS + 180))
  wait_service() {
    local svc="$1"
    while (( SECONDS < deadline )); do
      local health
      health="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$svc" 2>/dev/null || true)"
      if [[ "$health" == "healthy" ]]; then
        echo "[ok] $svc healthy"
        return 0
      fi
      if [[ -z "$health" ]] && docker inspect --format='{{.State.Status}}' "$svc" 2>/dev/null | grep -q running; then
        echo "[ok] $svc em execução"
        return 0
      fi
      sleep 3
    done
    echo "[warn] timeout aguardando $svc"
    return 1
  }
  for svc in yby-postgres yby-redis yby-litellm; do
    wait_service "$svc" || true
  done
  if docker ps --format '{{.Names}}' | grep -qxF yby-mosquitto; then
    echo "[ok] yby-mosquitto em execução"
  else
    echo "[warn] yby-mosquitto não encontrado"
  fi
else
  echo "[warn] docker compose indisponível — suba a stack manualmente: docker compose up -d"
fi

if command -v uv >/dev/null 2>&1; then
  echo "[ingest] docs/yby_seed_contracts.md → pgvector (domínio yby_arch)"
  uv sync --extra dev >/dev/null 2>&1 || uv sync >/dev/null 2>&1 || true
  uv run python -m src.yby_seed.memory.ingest --dir ./docs --domain yby_arch \
    || echo "[warn] ingest falhou (postgres/litellm/embeddings podem estar indisponíveis)"
else
  echo "[warn] uv não encontrado — instale uv antes do ingest"
fi

echo "== bootstrap concluído =="
