# Agente mínimo YBY (Tarefa 5)

Loop local: **Ollama** + três ferramentas (`search_knowledge`, `list_files`, `read_file`). Sem nuvem, sem multi-agente, sem autonomia ilimitada.

## Configuração (local)

| Variável | Padrão |
|----------|--------|
| `YBY_AGENT_OLLAMA_URL` / `YBY_OLLAMA_BASE_URL` | `http://localhost:11434` |
| `YBY_AGENT_MODEL` / `YBY_LOCAL_MODEL` | `qwen2.5:7b` (alternativa documentada: `qwen3:8b`) |
| `YBY_AGENT_TEMPERATURE` | `0.2` |
| `YBY_AGENT_NUM_CTX` | `8192` |
| `YBY_AGENT_LOG_PATH` | `logs/agent_runs.jsonl` |

## Módulos

- `loop.py` — orquestração (máx. 5 iterações, 3 tools), `trace_id`, resposta estruturada
- `runner.py` — Ollama `/api/generate` com temperatura e contexto
- `prompts.py` — system prompt pt-BR, RAG obrigatório em perguntas de projeto, citações
- `safety.py` — tamanho da pergunta, heurísticas anti-injeção
- `schemas.py` — passos JSON do planejador + `AgentStructuredResponse`

## Resposta estruturada

`AgentStructuredResponse`: `answer`, `sources`, `tools_used`, `confidence`, `needs_approval`, `warnings`, `trace_id`, `latency_ms`, `token_usage`, `status`.

## Integração RAG

Ver `docs/RAG_DESIGN.md`. O agente chama `search_knowledge` via `create_default_registry()`; chunks são dados, não comandos.

## Verificação

```bash
python3 -m pytest tests/test_agent_loop.py tests/test_agent_safety.py -q
```