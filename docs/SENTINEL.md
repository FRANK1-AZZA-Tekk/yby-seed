# Sentinela local

Motor separado do loop conversacional: **coletar → avaliar → notificar**.
Não usa n8n, Node-RED, LLM em segundo plano nem reparo automático.
**Nunca** reinicia o Ollama e **não** toca no vault.

## Regras (configuráveis)

| ID | Condição |
|---|---|
| `ollama_down` | Ollama indisponível por ≥ `ollama_down_seconds` (padrão 300) |
| `vault_backup_stale` | Arquivo `yby-vault-*.tar.gz` mais antigo que `backup_max_age_hours` |
| `vault_backup_unverified` | Não foi possível verificar o backup (dir ausente, sem arquivos, erro de I/O) — **distinto** de atrasado |

## Uso

```bash
cp config/sentinel.example.json ~/.config/yby-seed/sentinel.json
export YBY_SENTINEL_CONFIG=~/.config/yby-seed/sentinel.json
python yby.py sentinel once
python yby.py sentinel rules
```

Estado: `~/.local/state/yby-seed/sentinel/` (`incidents.json` + `runtime.json`).
O painel lê os incidentes ativos do mesmo `incidents.json`.

### Timer (opcional, sem enable automático)

```bash
bash scripts/install-sentinel-timer.sh          # só grava unidades
bash scripts/install-sentinel-timer.sh --enable # só se você pedir
```

Reaproveita o padrão systemd de usuário do PC Hub; **não** habilita serviços sozinho.

## Comportamento

- Um aviso por incidente; rearme só após recuperação (nova queda pode gerar outro).
- Reiniciar o processo **não** duplica o aviso (`notified_at` persistido).
- Pausa / horário silencioso (`quiet_hours`): não entrega; alerta fica `pending_notify`.
- Antes de notificar um pendente, **reavalia** a condição.
- Sem desktop (`notify-send` / DISPLAY): **não** marca como entregue.
- Via `assist`: `sentinel.rules.list` | `pause` | `resume` (pause/resume pedem confirmação).

## Fora de escopo

Habilitar serviços por padrão, reiniciar host/Ollama, simular sucesso sem desktop, Grafana.
