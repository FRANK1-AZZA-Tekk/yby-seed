# Backup restaurável do vault (D8 / fase P)

Script: `scripts/backup-vault.sh` (tar + gzip, sem dependências novas).

## Backup

```bash
export YBY_VAULT_PATH=~/Vaults/yby          # pasta sincronizada pelo Syncthing
export YBY_BACKUP_DIR=~/backups/yby-vault   # decisão P #4 / A (SSD local); /mnt/backup/yby-vault se/quando houver 2º disco
export YBY_BACKUP_KEEP=7                   # decisão P #5 / A — tar + retenção 7
bash scripts/backup-vault.sh
```

Agende no hub (cron ou timer systemd), por exemplo diário. O script **não** sobe Syncthing e **não** grava dentro do vault.

## Restauração (teste obrigatório no checklist)

```bash
# Pasta de destino deve estar vazia (o script recusa sobrescrever).
export YBY_VAULT_PATH=/tmp/yby-vault-restore-test
rm -rf "$YBY_VAULT_PATH"
bash scripts/backup-vault.sh --restore ~/backups/yby-vault/yby-vault-YYYYMMDD-HHMMSS.tar.gz
```

Critério de aceite da fase P: restaurar numa pasta vazia e conferir notas Markdown esperadas. Marque o item no [PHASE-P-CHECKLIST.md](PHASE-P-CHECKLIST.md) **só** após esse teste no hardware.

## Syncthing

Backup local ≠ Syncthing. Syncthing continua separado (`examples/syncthing/`). Comprove sync PC↔hub no hardware; este ambiente de CI/agente não valida Syncthing real.
