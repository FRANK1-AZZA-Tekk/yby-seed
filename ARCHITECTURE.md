# Arquitetura — YBY SEED

Visão do **v1 (PC Hub)**. Caminho legado de agentes (`src/agents/`) e gateway MQTT **não** entram no fluxo abaixo — ver [src/README.md](src/README.md) e [docs/REPOS.md](docs/REPOS.md).

## Visão geral

YBY SEED é um PC Hub **local-first**: CLI `yby.py`, Ollama (`qwen2.5-coder:3b`, D4), nuvem só quando o roteamento pede (D3/D12), vault Markdown e porta de segurança para shell. Mobile e ESP32 ficam fora do v1 ([docs/archive/FORA-DO-V1.md](docs/archive/FORA-DO-V1.md)).

## Caminho de produção (`ask` e amigos)

```text
Usuário
  ↓
yby.py → src/main.py (Click)
  ├─ ask [--heavy] [--voice]
  │     → src/engine (HybridEngine: Ollama, cache, roteamento, budget)
  │     → nuvem OpenRouter (primária) se pesado/explícito; sem failover auto → Grok (D12, #42)
  ├─ run "cmd"
  │     → src/safety (allowlist + sim/não) → src/actions (subprocess, timeout)
  ├─ gate "cmd" → src/safety (só decide)
  ├─ note / recall → src/memory (vault Obsidian, D8)
  ├─ listen / ask --voice → src/voice (Whisper/Piper, D11) → engine
  └─ hub → src/platform (keepalive Ollama, D9)
```

Código gerado (legado/agentes) pode passar por [src/security/ast_guard.py](src/security/ast_guard.py).

## Módulos no disco, fora do v1

| Área | Pasta | Nota |
|---|---|---|
| Agentes / planejamento antigo | `src/agents/`, `src/core/` | Não chamados pelo `ask` |
| RAG / vetores | `src/rag/` | Qdrant opcional ([docker-compose.yml](docker-compose.yml)) |
| Gateway HTTP/MQTT | `src/gateway/` | Loopback + `GATEWAY_TOKEN` se usado |
| Skills | `skills/` | Dry-run D6 — fase 3+ no [ROADMAP.md](ROADMAP.md) |
| Proxy de custo | [litellm_config.yaml](litellm_config.yaml) | Opcional; `ask` não depende dele |

Orquestração LangGraph/MQTT permanece em **yby-core** (repositório separado, D7).

## Serviços opcionais (fases futuras)

| Serviço | Função | Estado no repo |
|---|---|---|
| Qdrant | Memória semântica / RAG | Compose opcional, só legado RAG |
| FastAPI | API em `src/gateway` | Legado, não é o núcleo |
| PostgreSQL / Redis | Histórico / filas | Mencionados em docs antigos; não no caminho `ask` |

## Regras de arquitetura

- O **núcleo funciona sem Docker** (D5): venv + Ollama no host.
- **Local-first**; nuvem com chave no `.env` e política em [DECISIONS.md](DECISIONS.md) D3/D12.
- **Shell:** allowlist + confirmação (D10); `safety` não executa; `actions` executa.
- **Skills / automações:** dry-run antes de efeitos colaterais (D6) — alinhar ao integrar agentes.
- **Um serviço por vez** ao adicionar infra (Syncthing, Qdrant, gateway).

Detalhes operacionais: [docs/DEV.md](docs/DEV.md), [docs/PLATFORM.md](docs/PLATFORM.md), [ROADMAP.md](ROADMAP.md).