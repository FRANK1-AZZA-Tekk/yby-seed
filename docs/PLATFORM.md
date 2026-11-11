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

A unit fica em `~/.config/systemd/user/yby-hub.service`, gerada a partir de `scripts/yby-hub.service` (cópia espelho em `deploy/systemd/`). Usa o Python do `.venv` se existir.

Parar:

```bash
systemctl --user disable --now yby-hub.service
```

Login sem GUI: `loginctl enable-linger $USER`.

## Syncthing (vault)

O motor não sincroniza arquivos. Configure o Syncthing à parte e aponte `YBY_VAULT_PATH` para a pasta compartilhada.

- Exemplo YAML: [docs/syncthing/vault-folder.example.yaml](syncthing/vault-folder.example.yaml)
- Exemplo XML + passos: [examples/syncthing/](../examples/syncthing/)

## Nuvem (local-first)

1. **Ollama** local (`qwen2.5-coder:3b`) por padrão.
2. Pedidos pesados / `--heavy` → **OpenRouter** (`openrouter/free` por padrão).
3. Se OpenRouter falhar → **Grok (xAI)** (`YBY_GROK_*` / `XAI_API_KEY`).
4. Cache local com TTL (`YBY_CACHE_TTL_SECONDS`, padrão 3600; `0` desliga).
5. Contexto truncado antes da nuvem (`YBY_CLOUD_CONTEXT_MAX_CHARS`, padrão 12000).

Chaves só no `.env` (nunca no git). Template: [`.env.example`](../.env.example). Decisão: [DECISIONS.md](../DECISIONS.md) D3 / D9.

## Checklist no hub

1. `ollama serve` + `ollama pull qwen2.5-coder:3b`
2. `.env` com vault e chaves de nuvem (opcionais)
3. Syncthing na pasta do vault
4. `bash scripts/install-hub-service.sh --enable`
5. `python yby.py ask "oi"` para validar o caminho de texto
