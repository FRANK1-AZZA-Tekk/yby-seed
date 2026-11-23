# Decisões — Fase P (fechadas)

Escolhas do dono para a fase P. Atualizar [PHASE-P.md](PHASE-P.md) / [PLATFORM.md](PLATFORM.md) quando o estado de fato mudar.

**Status:** todas as 8 perguntas fechadas em **2026-11-19**. Nota do dono: *aceitou todas as sugestões*.

## Estado de fato (código vigente)

Isto descreve o que o repositório já faz hoje, alinhado às decisões fechadas abaixo.

| Tema | Estado de fato no código/scripts |
|------|----------------------------------|
| Unit systemd | Script `scripts/install-hub-service.sh` instala **unit de usuário** `~/.config/systemd/user/yby-hub.service`. |
| Escopo do daemon | Hub keepalive só (`python -m src.platform.hub` / `yby hub`); **não** sobe gateway FastAPI. |
| Dependência Ollama | Unit declara `After=network-online.target` e `After=ollama.service` (decisão #3 / A). Se Ollama não for unit systemd, o hub ainda registra falha e continua o loop. |
| Nome da unit | Nome vigente: `yby-hub.service`. |
| Syncthing | Fora do processo YBY; exemplos em `examples/syncthing/` e `docs/syncthing/`. Serviço de **usuário** (decisão #6 / A). |
| Backup vault | Script mínimo `scripts/backup-vault.sh` (tar + retenção 7); destino padrão `~/backups/yby-vault/` (decisão #4 / A). Destino via env — **não** comprovado no hardware deste ambiente. |
| Política nuvem vs falha Ollama | Caminho local: falha Ollama **não** chama nuvem (`HybridEngine._after_local_failure`, D12 / fase P). Hub na estabilização: **sem** chaves de nuvem no `.env` do servidor (decisão #8 / A). Nuvem só com roteamento pesado/`--heavy` + gate (após #42 / chaves). OpenRouter→Grok: sem failover automático (`CascadingCloudProvider`). |
| Issue #42 | JSONL + budget diário/mensal (tokens+USD) + exception 1-shot + sanitizer gated + confirm TTY; SQLite FinOps (S1) e authz vault ainda abertos. |

## Decisões fechadas (dono — 2026-11-19)

Nota: *dono aceitou todas as sugestões*.

### 1. Serviço por usuário ou sistema? → **A** (fechada)

- **Opção A:** unit **de usuário** (`systemctl --user`), mais simples e alinhada a `scripts/install-hub-service.sh`.
- **Opção B:** unit **de sistema** (`/etc/systemd/system`), mais robusta para máquina dedicada; exige root e política de secrets.
- **Recomendação (aceita):** Opção A (usuário atual + `loginctl enable-linger`).

### 2. Escopo do daemon no boot → **A** (fechada)

- **Opção A:** apenas **hub keepalive** (checa Ollama; já existe no repo).
- **Opção B:** hub + **gateway** FastAPI na mesma unit (mais superfície; exige `GATEWAY_TOKEN` e revisão de bind).
- **Recomendação (aceita):** Opção A até D12 e log de nuvem (#42) estarem estáveis.

### 3. Dependência explícita do Ollama no systemd → **A** (fechada)

- **Opção A:** unit do YBY com `After=ollama.service` (se Ollama for serviço systemd).
- **Opção B:** sem `After`; o hub só registra falha e reinicia (comportamento anterior do keepalive).
- **Recomendação (aceita):** Opção A quando Ollama estiver instalado como serviço; unit do repo passa a declarar `After=ollama.service`.

### 4. Destino dos backups do vault → **A** (fechada)

- **Opção A:** diretório local no mesmo SSD (`~/backups/yby-vault/`).
- **Opção B:** segundo disco ou partição montada (`/mnt/backup/yby-vault/`).
- **Recomendação (aceita):** Opção B *quando* houver disco extra; **senão A** com retenção de 7 cópias. Sem disco extra comprovado no hub → **A** (`YBY_BACKUP_DIR=~/backups/yby-vault`, `YBY_BACKUP_KEEP=7`).

### 5. Ferramenta de backup → **A** (fechada)

- **Opção A:** `tar` + rotação por data (sem dependência nova).
- **Opção B:** `restic` ou `borg` (deduplicação, mais setup).
- **Recomendação (aceita):** Opção A no v1 da fase P.

### 6. Syncthing: usuário ou sistema? → **A** (fechada)

- **Opção A:** Syncthing como serviço de **usuário** (padrão upstream).
- **Opção B:** Syncthing de **sistema** para vault compartilhado entre logins.
- **Recomendação (aceita):** Opção A, mesma conta que roda o YBY.

### 7. Nome e visibilidade da unit → **A** (fechada)

- **Opção A:** manter `yby-hub.service` (como nos scripts atuais).
- **Opção B:** renomear para `yby-seed.service` (exige aceite para mudar scripts na PR de implementação).
- **Recomendação (aceita):** Opção A até haver PR dedicada.

### 8. Política de nuvem na fase P → **A** (fechada)

- **Opção A:** Hub **sem** chaves de nuvem no `.env` do servidor (só Ollama; máximo isolamento).
- **Opção B:** Chaves presentes, mas D12 + confirmação + log (#42) antes de qualquer uso.
- **Recomendação (aceita):** Opção A na estabilização inicial; Opção B só após merge da issue #42.

---

## Registro SIM/NÃO (histórico)

1. Serviço usuário (A) vs sistema (B)? → **SIM** (A)
2. Daemon só hub (A) vs hub+gateway (B)? → **SIM** (A)
3. `After=ollama.service` (A) vs sem After (B)? → **SIM** (A)
4. Backup no SSD local (A) vs segundo disco (B)? → **SIM** (A — sem disco extra; B se/quando houver)
5. Ferramenta `tar` (A) vs restic/borg (B)? → **SIM** (A)
6. Syncthing usuário (A) vs sistema (B)? → **SIM** (A)
7. Manter `yby-hub.service` (A) vs renomear (B)? → **SIM** (A)
8. Hub sem chaves nuvem (A) vs chaves + D12/#42 (B)? → **SIM** (A)

Marcar a fase P como **estável** no [ROADMAP.md](../ROADMAP.md) continua **somente** com aprovação explícita do dono após o checklist de hardware.
