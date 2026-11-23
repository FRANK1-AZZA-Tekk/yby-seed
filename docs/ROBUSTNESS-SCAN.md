# Scan de robustez — plano em camadas (pós visão + IoT)

Mapeamento e correções incrementais. Um PR por camada; métricas finais em `docs/PERFORMANCE.md` (PR-7).

| PR | Camada | Status |
| :--- | :--- | :--- |
| PR-1 | `src/core`, `src/engine`, `src/agent_loop` | Concluído (#113) |
| **PR-A** | Revisão da camada 1 (pós-merge #113) | Em review |
| PR-2 / PR-B | `src/memory`, `src/rag` | Pendente |
| PR-3 / PR-C | `src/iot` | Pendente |
| PR-4 | `src/voice`, `src/vision` | Pendente |
| PR-5 | `src/safety`, `src/security` | Pendente |
| PR-6 | `src/gateway`, `src/monitoring` | Pendente |
| PR-7 | Transversal + `docs/PERFORMANCE.md` | Pendente |

Detalhes de cada entrega: `PROGRESS.md` (seção Robustez PR-n / PR-A).

## Skips conhecidos (`pytest -rs`)

Captura em 2026-11-23 (**324 passed, 14 skipped**). Saída completa: `/opt/cursor/artifacts/pytest-rs-pr-a.txt`.

| Área | Qtd | Motivo |
| :--- | ---: | :--- |
| `tests/test_agents.py` | 8 | Agentes (Router/Planning/Execution/Validation/Learning) ainda não implementados |
| `tests/test_gateway.py` | 3 | Gateway depende de Ollama/PostgreSQL/MQTT — fixtures pendentes |
| `tests/test_rag.py` | 3 | RAG depende de embeddings reais — fixtures pendentes |

## PR-A — checklist (core / engine / agent_loop)

| Item | Estado |
| :--- | :--- |
| HTTP retry/backoff (`_post_with_retry`, 408/429/502/503/504) | OK (#113) |
| `HybridEngine.close()` / provedores | OK (#113) |
| `tool_timeout_seconds` no `ControlledAgentLoop` | OK (#113) |
| `OllamaClientError` + timeouts no legado | OK (#113) |
| Exceção não prevista em tool → `status=error` (sem crash) | Corrigido (PR-A) |
| `yby ask` / `yby agent --local` sem `close()` explícito no CLI | Follow-up (fora de `src/agent_loop`) |