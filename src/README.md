# `src/` — layout do pacote

Pacote Python do YBY SEED (`pythonpath = ["."]` no `pyproject.toml`). Entrada CLI: `yby.py` → `src.main`.

## Caminho de produção (v1 / `ask` e amigos)

| Pacote | Papel |
|---|---|
| `engine/` | HybridEngine, roteamento local/nuvem, cache |
| `safety/` | allowlist + decisão (não executa) |
| `actions/` | subprocess após a porta (timeout/saída/bloqueio scaffold) |
| `conversation/` | envelope professor PT-BR (`ask --explain`, gate/run) |
| `brief/` | YBY-BRIEF (entrevista → proposta; sem código) |
| `plan/` | YBY-PLAN (etapas vs allowlist; sem execução) |
| `cursor_fake/` | dry-run de plano validated (`yby cursor-fake`; sem MCP) |
| `learn/` | aprendizado diário JSONL + relatório (`yby learn`; sem auto-merge) |
| `research/` | pesquisa consentida com HTTP fake (`yby research`; sem busca real) |
| `devices/` | contratos `yby-device/v1` + bus fake (`yby devices`; sem firmware) |
| `artifacts/` | scaffold Python CLI + manifesto (sem install) |
| `memory/` | vault Markdown + prefs com consentimento (`yby prefs`) |
| `backup/` | backup local vault + logs redigidos (`yby backup`) |
| `obs/` | CLI `yby usage` sobre `cloud_usage.jsonl` |
| `voice/` | STT/TTS opcional (`listen` / `ask --voice`) |
| `platform/` | hub keepalive (serviço systemd) |
| `security/ast_guard.py` | guarda de código gerado |
| `main.py` | Click CLI |

## Presente no disco, fora do `ask`

Não apague em massa. Trate como legado / futuro até uma decisão explícita:

| Pasta | Nota |
|---|---|
| `agent_loop/` | loop P0 controlado (`yby agent`); fora do `ask` |
| `agents/` | stubs/agentes antigos (Router, Planning, …); ver `agents/README.md` |
| `core/` | cliente Ollama e helpers usados por agentes, não pelo HybridEngine |
| `rag/` | otimizações RAG; fora do fluxo atual |
| `gateway/` | FastAPI/MQTT; loopback + token se usado |
| `skills/`, `monitoring/`, `evaluation/` | suporte / métricas; não no CLI do v1 |

Detalhe de camadas e outros repos: [docs/REPOS.md](../docs/REPOS.md).
