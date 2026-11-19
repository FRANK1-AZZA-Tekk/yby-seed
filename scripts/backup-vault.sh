#!/usr/bin/env bash
# Backup restaurável do vault Obsidian (D8 / fase P).
# Sem dependências novas: tar + gzip + retenção por contagem.
#
# Uso:
#   export YBY_VAULT_PATH=~/Vaults/yby
#   bash scripts/backup-vault.sh
#   bash scripts/backup-vault.sh --restore /caminho/para/yby-vault-YYYYMMDD-HHMMSS.tar.gz
#
# Env:
#   YBY_VAULT_PATH     pasta do vault (obrigatória para backup)
#   YBY_BACKUP_DIR     destino (padrão: ~/backups/yby-vault)
#   YBY_BACKUP_KEEP    quantas cópias manter (padrão: 7)
set -euo pipefail

KEEP="${YBY_BACKUP_KEEP:-7}"
BACKUP_DIR="${YBY_BACKUP_DIR:-${HOME}/backups/yby-vault}"

usage() {
  echo "Uso: $0 [--restore ARQUIVO.tar.gz]"
  echo "  Backup: precisa de YBY_VAULT_PATH; grava em YBY_BACKUP_DIR (padrão ~/backups/yby-vault)."
  echo "  Restore: extrai para YBY_VAULT_PATH (não sobrescreve se a pasta já tiver arquivos)."
}

restore_one() {
  local archive="$1"
  if [[ -z "${YBY_VAULT_PATH:-}" ]]; then
    echo "Defina YBY_VAULT_PATH para o destino da restauração." >&2
    exit 1
  fi
  if [[ ! -f "$archive" ]]; then
    echo "Arquivo não encontrado: $archive" >&2
    exit 1
  fi
  local dest
  dest="$(mkdir -p "$(dirname "${YBY_VAULT_PATH}")" && mkdir -p "${YBY_VAULT_PATH}" && cd "${YBY_VAULT_PATH}" && pwd)"
  if [[ -n "$(ls -A "$dest" 2>/dev/null || true)" ]]; then
    echo "Recusa: ${dest} não está vazia. Esvazie ou aponte YBY_VAULT_PATH para pasta nova." >&2
    exit 1
  fi
  tar -xzf "$archive" -C "$dest"
  echo "Restaurado em: $dest"
  echo "Fonte: $archive"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "${1:-}" == "--restore" ]]; then
  if [[ -z "${2:-}" ]]; then
    usage >&2
    exit 1
  fi
  restore_one "$2"
  exit 0
fi

if [[ -z "${YBY_VAULT_PATH:-}" ]]; then
  echo "Defina YBY_VAULT_PATH." >&2
  exit 1
fi

VAULT="$(cd "${YBY_VAULT_PATH}" && pwd)"
mkdir -p "${BACKUP_DIR}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
ARCHIVE="${BACKUP_DIR}/yby-vault-${STAMP}.tar.gz"

# Empacota o conteúdo (sem path absoluto no tar).
tar -czf "${ARCHIVE}" -C "${VAULT}" .
echo "Backup criado: ${ARCHIVE}"
echo "Vault: ${VAULT}"

# Retenção: apaga os mais antigos além de KEEP.
mapfile -t OLD < <(ls -1t "${BACKUP_DIR}"/yby-vault-*.tar.gz 2>/dev/null || true)
if ((${#OLD[@]} > KEEP)); then
  for f in "${OLD[@]:KEEP}"; do
    rm -f -- "$f"
    echo "Removido (retenção ${KEEP}): $f"
  done
fi

echo "Cópias em ${BACKUP_DIR}: $(ls -1 "${BACKUP_DIR}"/yby-vault-*.tar.gz 2>/dev/null | wc -l)"
echo "Teste de restauração (pasta vazia):"
echo "  YBY_VAULT_PATH=/tmp/yby-vault-restore-test bash $0 --restore ${ARCHIVE}"
