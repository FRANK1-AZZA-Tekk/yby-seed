#!/usr/bin/env bash
# Instala o serviço de usuário systemd do YBY hub (keepalive).
# Uso (na pasta do repo, com venv opcional):
#   bash scripts/install-hub-service.sh
#   bash scripts/install-hub-service.sh --enable
set -euo pipefail

ENABLE=0
for arg in "$@"; do
  case "$arg" in
    --enable|--enable-now) ENABLE=1 ;;
    -h|--help)
      echo "Uso: $0 [--enable]"
      echo "Instala ~/.config/systemd/user/yby-hub.service"
      exit 0
      ;;
    *)
      echo "Argumento desconhecido: $arg" >&2
      exit 1
      ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_SRC="${ROOT}/scripts/yby-hub.service"
UNIT_DIR="${HOME}/.config/systemd/user"
UNIT_DST="${UNIT_DIR}/yby-hub.service"

if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PYTHON="${ROOT}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
else
  echo "python3 não encontrado" >&2
  exit 1
fi

mkdir -p "${UNIT_DIR}"
sed \
  -e "s|__YBY_ROOT__|${ROOT}|g" \
  -e "s|__YBY_PYTHON__|${PYTHON}|g" \
  "${UNIT_SRC}" > "${UNIT_DST}"

systemctl --user daemon-reload
echo "Unidade instalada em ${UNIT_DST}"
echo "Python: ${PYTHON}"
echo "Root:   ${ROOT}"

if [[ "${ENABLE}" -eq 1 ]]; then
  systemctl --user enable --now yby-hub.service
  systemctl --user --no-pager --full status yby-hub.service || true
  echo "Habilitado com: systemctl --user enable --now yby-hub.service"
else
  echo "Para ativar: systemctl --user enable --now yby-hub.service"
  echo "Ou rode de novo: bash scripts/install-hub-service.sh --enable"
fi

echo "Dica (login sem GUI): loginctl enable-linger \$USER"
