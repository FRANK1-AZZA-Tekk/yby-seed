# Checklist — Fase P (PC Hub sempre ligado)

Marcar conforme execução no hardware real. Alinhado a [PHASE-P.md](PHASE-P.md) e [PHASE-P-DECISIONS.md](PHASE-P-DECISIONS.md).

**Não marque itens como feitos sem hardware.** Agentes/CI não substituem reboot, Syncthing real nem restauração no PC Hub.

## Verificação parcial (repo / CI / cloud agent)

Antes do Hub, rode o runner local — ele só marca o que é verificável em arquivos/docs/`make doctor`; o resto fica `SKIP`/`PENDING`:

```bash
bash scripts/phase-p-check.sh
```

Saída típica: `PASS` (unit `After=ollama`, backup script, `.stignore` com `.yby/`, 8 decisões fechadas, doctor) + muitos `SKIP` de hardware. **FAIL** = regressão no repo; corrija antes de ir ao Hub.

## Como rodar no Hub (guia rápido)

Ordem sugerida com as [decisões do dono fechadas](PHASE-P-DECISIONS.md) (8/8 em 2026-11-19; todas as recomendações):

1. Inventário (Fase 1): usuário Linux, `YBY_VAULT_PATH`, Python, `ollama list`, Syncthing instalado.
2. Serviço: `bash scripts/install-hub-service.sh --enable` → `systemctl --user status yby-hub` → `loginctl enable-linger $USER` se login sem GUI.
3. Saúde: `python yby.py hub --once` e reboot completo (Fase 3 / Fase 6).
4. Syncthing (serviço de usuário): só a pasta do vault; ver `examples/syncthing/` + `.stignore.example` (Fase 4).
5. Backup: `YBY_BACKUP_DIR=~/backups/yby-vault` + `bash scripts/backup-vault.sh` e restauração em pasta vazia — [BACKUP.md](BACKUP.md) (Fase 5).
6. Nuvem: hub **sem** chaves no `.env` na estabilização; confirmar que falha de Ollama **não** chama nuvem (D12 / #42).

Itens abaixo continuam para execução no **hardware real** — não marcar como feitos só por docs/CI / `phase-p-check.sh`.

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

- [ ] Criar backup local diário.
- [ ] Manter no mínimo 7 backups.
- [ ] Testar restauração real.
- [ ] Garantir que backup não sobrescreva o vault.
- [ ] Registrar local e retenção.

## Fase 6 — Validação final

- [ ] Reboot completo.
- [ ] Falha simulada do serviço.
- [ ] Falha simulada do Ollama.
- [ ] Falha simulada de rede.
- [ ] Restauração do backup.
- [ ] Nenhuma chamada de nuvem sem autorização.
