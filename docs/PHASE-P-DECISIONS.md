# Decisões pendentes — Fase P

Escolhas do dono antes de fechar a fase P. Após cada decisão, atualizar [PHASE-P.md](PHASE-P.md) ou [PLATFORM.md](PLATFORM.md) somente quando aprovado (fora desta tarefa de spec).

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

Quando todas as decisões acima estiverem fechadas, marcar a fase P como **estável** no [ROADMAP.md](../ROADMAP.md) — somente com aprovação explícita do dono.
