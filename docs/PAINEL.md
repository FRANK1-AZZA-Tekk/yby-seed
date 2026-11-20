# Painel local de consulta (PR1, somente leitura)

UI mínima em loopback para inspecionar o estado do assist, alertas do Sentinela e camadas do develop — **sem** executar nada.

## Subir

```bash
export YBY_PAINEL_TOKEN="$(openssl rand -hex 16)"   # ou linha no .env
python yby.py painel                 # 127.0.0.1:8765
python yby.py painel --port 8765
```

- Bind fixo em loopback (`127.0.0.1` / `localhost` / `::1`). Host `0.0.0.0` é recusado.
- Sem `YBY_PAINEL_TOKEN` → CLI aborta; HTTP responde **503**.
- Token errado / ausente no request → **401**, zero dados.
- Header: `Authorization: Bearer …` ou `X-API-Token: …`.

```bash
curl -s -H "Authorization: Bearer $YBY_PAINEL_TOKEN" http://127.0.0.1:8765/api/resumo | jq .
```

## Rotas

| Método | Caminho | Resposta |
|---|---|---|
| `GET` | `/` | HTML escapado (cartões) |
| `GET` | `/api/resumo` | JSON do mesmo resumo |

Não há endpoints de execução, shell, captura ou input sintético.

## Fontes (uma por domínio — writers)

| Domínio | Path padrão | Writer |
|---|---|---|
| Rotinas | `~/.local/state/yby-seed/assist-audit.jsonl` (`tool=routine.run`) | `assist` (executor) |
| Lembretes | `~/.local/state/yby-seed/assist-reminders.json` | `assist` |
| Alertas | `~/.local/state/yby-seed/sentinel/incidents.json` | Sentinela (PR #92; `yby sentinel once`) |
| Develop | `~/.local/state/yby-seed/develop/plans/*.json` (fallback `.yby/develop/plans/`) | `yby develop` ([DEV_DEVELOP.md](DEV_DEVELOP.md)) |
| Ollama | `check_ollama` | hub / assist (somente leitura no painel) |

O painel **só lê** esses arquivos. Não cria segunda fonte de verdade.

Estados de item na UI: `proposto` | `executado` | `falhou` | `aguardando_aprovacao`.

- Rotina parcial: meta do audit com `ran` / `failed` / `skipped`.
- Camada develop `preparada`/`enviada` → `aguardando_aprovacao`.
- Arquivos ausentes → listas vazias.

## Segurança

- HTML: `html.escape` em todo campo dinâmico (notas/logs como texto).
- Token do painel **não** é o `GATEWAY_TOKEN` do MQTT/gateway.
- Cores só via classes CSS estáticas (`state-falhou`, etc.).

## Fora de escopo do painel

Endpoints de aprovação/execução, `assist --voice`, Grafana/Prometheus.
