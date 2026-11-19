# Plataforma — PC Hub sempre ligado (D9)

O YBY SEED roda num servidor doméstico (Ubuntu). Esta página cobre o **serviço keepalive**, o **Syncthing do vault** e as variáveis de nuvem. Não é o gateway MQTT/FastAPI (`src/gateway`).

## Hub keepalive

Processo fino que só verifica se o Ollama responde e registra no journal. Reinicia com o systemd.

```bash
# Manual (uma checagem)
python -m src.platform.hub --once
# ou
python yby.py hub --once

# Loop (intervalo via YBY_HUB_INTERVAL, padrão 60s)
python -m src.platform.hub
```

### systemd (usuário)

```bash
bash scripts/install-hub-service.sh --enable
systemctl --user status yby-hub.service
```

A unit fica em `~/.config/systemd/user/yby-hub.service`, gerada a partir de `scripts/yby-hub.service` (cópia espelho em `deploy/systemd/`). Declara `After=network-online.target ollama.service` (decisão P #3). Usa o Python do `.venv` se existir. Decisões da fase P: [PHASE-P-DECISIONS.md](PHASE-P-DECISIONS.md).

Parar:

```bash
systemctl --user disable --now yby-hub.service
```

Login sem GUI: `loginctl enable-linger $USER`.

## Syncthing (vault)

O motor não sincroniza arquivos. Configure o Syncthing à parte (serviço de **usuário**, mesma conta do YBY — decisão P #6 / A) e aponte `YBY_VAULT_PATH` para a pasta compartilhada. Sincronize **apenas** o vault — não o clone do repositório.

- Exemplo YAML: [docs/syncthing/vault-folder.example.yaml](syncthing/vault-folder.example.yaml)
- Exemplo XML + passos + `.stignore` (`.yby/`, caches): [examples/syncthing/](../examples/syncthing/)
- Serviço: `systemctl --user enable --now syncthing` (+ `loginctl enable-linger $USER` se login sem GUI). Não instalar Syncthing via este repositório/CI.

## Nuvem (local-first)

1. **Ollama** local (`qwen2.5-coder:3b`) por padrão.
2. Pedidos pesados / `--heavy` → **OpenRouter** (`openrouter/free` por padrão), com confirmação TTY e log local (#42).
3. Se o Ollama falhar no caminho local → **não** chama nuvem automaticamente (D12 / fase P / #42).
4. Se OpenRouter falhar → mensagem de erro; **não** há failover automático para Grok (D12; issue #42). Grok (`YBY_GROK_*`) é destino configurável para evolução futura.
5. Cache local com TTL (`YBY_CACHE_TTL_SECONDS`, padrão 3600; `0` desliga).
6. Contexto truncado antes da nuvem (`YBY_CLOUD_CONTEXT_MAX_CHARS`, padrão 12000).

Na estabilização da fase P (decisão #8 / A): **não** colocar chaves de nuvem no `.env` do hub — só Ollama. Quando houver chaves, só no `.env` (nunca no git) e só com D12 + log (#42). Template: [`.env.example`](../.env.example). Decisões: [DECISIONS.md](../DECISIONS.md) D3, D9, D12.

## Backup do vault

Script mínimo: `bash scripts/backup-vault.sh` (`tar` + retenção 7; destino padrão `~/backups/yby-vault/` — decisões P #4/#5). Detalhe e restauração: [BACKUP.md](BACKUP.md).

## Checklist no hub

1. `ollama serve` + `ollama pull qwen2.5-coder:3b`
2. `.env` com vault; **sem** chaves de nuvem na estabilização (P #8)
3. Syncthing (usuário) na pasta do vault
4. `bash scripts/install-hub-service.sh --enable`
5. `python yby.py ask "oi"` para validar o caminho de texto
