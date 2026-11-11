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
