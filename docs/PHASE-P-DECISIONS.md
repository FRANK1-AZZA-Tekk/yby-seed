# Decisões pendentes — Fase P

Escolhas do dono antes de fechar a fase P. Após cada decisão, atualizar [PHASE-P.md](PHASE-P.md) ou [PLATFORM.md](PLATFORM.md) somente quando aprovado (fora desta tarefa de spec).

## Estado de fato (código vigente — não é decisão do dono)

Isto descreve o que o repositório já faz hoje. **Não** substitui as 8 decisões abaixo.

| Tema | Estado de fato no código/scripts |
|------|----------------------------------|
| Unit systemd | Script `scripts/install-hub-service.sh` instala **unit de usuário** `~/.config/systemd/user/yby-hub.service`. |
| Escopo do daemon | Hub keepalive só (`python -m src.platform.hub` / `yby hub`); **não** sobe gateway FastAPI. |
| Dependência Ollama | Unit atual **não** declara `After=ollama.service`; o hub registra falha e continua o loop. |
| Nome da unit | Nome vigente: `yby-hub.service`. |
| Syncthing | Fora do processo YBY; exemplos em `examples/syncthing/` e `docs/syncthing/`. |
| Backup vault | Script mínimo `scripts/backup-vault.sh` (tar + retenção); destino via env — **não** comprovado no hardware deste ambiente. |
| Política nuvem vs falha Ollama | Caminho local: falha Ollama **não** chama nuvem (`HybridEngine._after_local_failure`, D12 / fase P). Nuvem só com roteamento pesado/`--heavy` + gate de confirmação/orçamento. OpenRouter→Grok: sem failover automático (`CascadingCloudProvider`). |
| Issue #42 | Log JSONL + budget + confirm TTY já existem; SQLite FinOps da spec ainda é alvo futuro. |

## Decisões pendentes

### 1. Serviço por usuário ou sistema?

- **Opção A:** unit **de usuário** (`systemctl --user`), mais simples e alinhada a `scripts/install-hub-service.sh`.
- **Opção B:** unit **de sistema** (`/etc/systemd/system`), mais robusta para máquina dedicada; exige root e política de secrets.
- **Recomendação:** Opção A (usuário atual + `loginctl enable-linger`).

### 2. Escopo do daemon no boot

- **Opção A:** apenas **hub keepalive** (checa Ollama; já existe no repo).
- **Opção B:** hub + **gateway** FastAPI na mesma unit (mais superfície; exige `GATEWAY_TOKEN` e revisão de bind).
- **Recomendação:** Opção A até D12 e log de nuvem (#42) estarem estáveis.

### 3. Dependência explícita do Ollama no systemd

- **Opção A:** unit do YBY com `After=ollama.service` (se Ollama for serviço systemd).
- **Opção B:** sem `After`; o hub só registra falha e reinicia (comportamento atual do keepalive).
- **Recomendação:** Opção A se Ollama estiver instalado como serviço; senão B.

### 4. Destino dos backups do vault

- **Opção A:** diretório local no mesmo SSD (`~/backups/yby-vault/`).
- **Opção B:** segundo disco ou partição montada (`/mnt/backup/yby-vault/`).
- **Recomendação:** Opção B quando houver disco extra; senão A com retenção de 7 cópias.

### 5. Ferramenta de backup

- **Opção A:** `tar` + rotação por data (sem dependência nova).
- **Opção B:** `restic` ou `borg` (deduplicação, mais setup).
- **Recomendação:** Opção A no v1 da fase P.

### 6. Syncthing: usuário ou sistema?

- **Opção A:** Syncthing como serviço de **usuário** (padrão upstream).
- **Opção B:** Syncthing de **sistema** para vault compartilhado entre logins.
- **Recomendação:** Opção A, mesma conta que roda o YBY.

### 7. Nome e visibilidade da unit

- **Opção A:** manter `yby-hub.service` (como nos scripts atuais).
- **Opção B:** renomear para `yby-seed.service` (exige aceite para mudar scripts na PR de implementação).
- **Recomendação:** Opção A até haver PR dedicada; o critério de aceite da fase P aceita o nome acordado aqui.

### 8. Política de nuvem na fase P

- **Opção A:** Hub **sem** chaves de nuvem no `.env` do servidor (só Ollama; máximo isolamento).
- **Opção B:** Chaves presentes, mas D12 + confirmação + log (#42) antes de qualquer uso.
- **Recomendação:** Opção A na estabilização inicial; Opção B só após merge da issue #42.

---

## Respostas do dono (preencher)

Copie e responda só com **SIM** (aceita a recomendação) ou **NÃO** + letra da opção desejada. Não inventar respostas por agente.

1. Serviço usuário (A) vs sistema (B)? → _____
2. Daemon só hub (A) vs hub+gateway (B)? → _____
3. `After=ollama.service` (A) vs sem After (B)? → _____
4. Backup no SSD local (A) vs segundo disco (B)? → _____
5. Ferramenta `tar` (A) vs restic/borg (B)? → _____
6. Syncthing usuário (A) vs sistema (B)? → _____
7. Manter `yby-hub.service` (A) vs renomear (B)? → _____
8. Hub sem chaves nuvem (A) vs chaves + D12/#42 (B)? → _____

Quando todas as decisões acima estiverem fechadas, marcar a fase P como **estável** no [ROADMAP.md](../ROADMAP.md) — somente com aprovação explícita do dono.
