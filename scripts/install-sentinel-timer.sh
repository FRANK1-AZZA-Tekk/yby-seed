#!/usr/bin/env bash
# Instala unidade + timer do Sentinela (NÃO habilita por padrão).
# Uso:
#   bash scripts/install-sentinel-timer.sh
#   bash scripts/install-sentinel-timer.sh --enable
set -euo pipefail

ENABLE=0
for arg in "$@"; do
  case "$arg" in
    --enable|--enable-now) ENABLE=1 ;;
    -h|--help)
      echo "Uso: $0 [--enable]"
      echo "Instala ~/.config/systemd/user/yby-sentinel.{service,timer}"
      echo "Sem --enable: só grava os arquivos (não ativa o timer)."
      exit 0
      ;;
    *)
      echo "Argumento desconhecido: $arg" >&2
      exit 1
      ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_DIR="${HOME}/.config/systemd/user"
ENV_FILE="${YBY_ENV_FILE:-${HOME}/.config/yby-seed/.env}"

if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PYTHON="${ROOT}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
else
  echo "python3 não encontrado" >&2
  exit 1
fi

mkdir -p "${UNIT_DIR}"
mkdir -p "$(dirname "${ENV_FILE}")"

for name in yby-sentinel.service yby-sentinel.timer; do
  sed \
    -e "s|__YBY_ROOT__|${ROOT}|g" \
    -e "s|__YBY_PYTHON__|${PYTHON}|g" \
    -e "s|^EnvironmentFile=.*|EnvironmentFile=-${ENV_FILE}|" \
    "${ROOT}/scripts/${name}" > "${UNIT_DIR}/${name}"
done

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload 2>/dev/null || \
    echo "Aviso: systemctl --user indisponível; unidades em ${UNIT_DIR}" >&2
else
  echo "Aviso: systemctl não encontrado; unidades em ${UNIT_DIR}" >&2
fi

echo "Unidades em ${UNIT_DIR}/yby-sentinel.{service,timer}"
echo "Python: ${PYTHON}"
echo "Root:   ${ROOT}"

if [[ "${ENABLE}" -eq 1 ]]; then
  systemctl --user enable --now yby-sentinel.timer
  systemctl --user --no-pager --full status yby-sentinel.timer || true
  echo "Timer habilitado."
else
  echo "Timer NÃO habilitado (padrão)."
  echo "Para ativar depois: systemctl --user enable --now yby-sentinel.timer"
  echo "Ou: bash scripts/install-sentinel-timer.sh --enable"
fi
