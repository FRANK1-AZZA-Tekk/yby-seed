# Checklist — Fase P (PC Hub sempre ligado)

Marcar conforme execução no hardware real. Alinhado a [PHASE-P.md](PHASE-P.md) e [PHASE-P-DECISIONS.md](PHASE-P-DECISIONS.md).

## Fase 1 — Inventário

- [ ] Confirmar usuário Linux e diretório do projeto.
- [ ] Confirmar caminho do vault Obsidian.
- [ ] Confirmar Python e versão.
- [ ] Confirmar Ollama instalado e modelo disponível.
- [ ] Confirmar Syncthing instalado.

## Fase 2 — Serviço systemd

- [ ] Criar unidade systemd apenas para o usuário atual, se possível.
- [ ] Definir `Restart=on-failure`.
- [ ] Definir `RestartSec`.
- [ ] Definir `After=network-online.target`.
- [ ] Definir `Wants=network-online.target`.
- [ ] Definir `WorkingDirectory`.
- [ ] Definir `EnvironmentFile`.
- [ ] Garantir que segredos fiquem fora do repositório.

## Fase 3 — Boot e saúde

- [ ] Habilitar serviço no boot.
- [ ] Testar reboot.
- [ ] Criar comando de status.
- [ ] Criar log local.
- [ ] Validar que o serviço não expõe porta pública.

## Fase 4 — Syncthing

- [ ] Sincronizar apenas a pasta do vault.
- [ ] Ignorar `.yby/`, caches e arquivos temporários.
- [ ] Validar sincronização entre PC e servidor.
- [ ] Garantir que segredos não entrem na pasta sincronizada.

## Fase 5 — Backup

Ferramenta no repo: `python yby.py backup create|list|restore` (`src/backup/`).
Padrão: `YBY_BACKUP_DIR=backups/yby`, `YBY_BACKUP_KEEP=7`. Restore **sempre** para pasta alvo (não o vault vivo).

Teste documentado (CI cobre roundtrip; no hub real marque abaixo):

```bash
export YBY_VAULT_PATH=/caminho/do/vault
python yby.py backup create
python yby.py backup list
python yby.py backup restore backups/yby/yby-backup-….tar.gz /tmp/yby-restore-test
diff -ru "$YBY_VAULT_PATH" /tmp/yby-restore-test   # notas devem bater
# NÃO: restore direto em cima de $YBY_VAULT_PATH
```

- [ ] Criar backup local diário (timer/cron do SO chamando `yby backup create`).
- [ ] Manter no mínimo 7 backups (`YBY_BACKUP_KEEP=7`).
- [ ] Testar restauração real (comandos acima no hub).
- [x] Garantir que backup não sobrescreva o vault (restore recusa alvo não vazio sem `--force`).
- [x] Registrar local e retenção (`.env.example` + `DEV.md`).

## Fase 6 — Validação final

- [ ] Reboot completo.
- [ ] Falha simulada do serviço.
- [ ] Falha simulada do Ollama.
- [ ] Falha simulada de rede.
- [ ] Restauração do backup.
- [ ] Nenhuma chamada de nuvem sem autorização.
