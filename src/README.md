# `src/` — layout do pacote

Pacote Python do YBY SEED (`pythonpath = ["."]` no `pyproject.toml`). Entrada CLI: `yby.py` → `src.main`.

## Caminho de produção (v1 / `ask` e amigos)

| Pacote | Papel |
|---|---|
| `engine/` | HybridEngine, roteamento local/nuvem |
| `safety/` | allowlist + decisão (não executa) |
| `actions/` | subprocess após a porta |
| `memory/` | vault Markdown |
| `voice/` | STT/TTS opcional (`listen` / `ask --voice`) |
| `security/ast_guard.py` | guarda de código gerado |
| `main.py` | Click CLI |

## Presente no disco, fora do `ask`

Não apague em massa. Trate como legado / futuro até uma decisão explícita:

| Pasta | Nota |
|---|---|
| `agents/` | stubs/agentes antigos (Router, Planning, …); ver `agents/README.md` |
| `core/` | cliente Ollama e helpers usados por agentes, não pelo HybridEngine |
| `rag/` | otimizações RAG; fora do fluxo atual |
| `gateway/` | FastAPI/MQTT; loopback + token se usado |
| `skills/`, `monitoring/`, `evaluation/` | suporte / métricas; não no CLI do v1 |

Detalhe de camadas e outros repos: [docs/REPOS.md](../docs/REPOS.md).
