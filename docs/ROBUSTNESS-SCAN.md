# Scan de robustez — plano em camadas (pós visão + IoT)

Mapeamento e correções incrementais. Um PR por camada; métricas finais em `docs/PERFORMANCE.md` (PR-7).

| PR | Camada | Status |
| :--- | :--- | :--- |
| **PR-1** | `src/core`, `src/engine`, `src/agent_loop` | Concluído (#113) |
| **PR-2** | `src/memory`, `src/rag` | Em review |
| **PR-3** | `src/iot` | Em review |
| PR-4 | `src/voice`, `src/vision` | Pendente |
| PR-5 | `src/safety`, `src/security` | Pendente |
| PR-6 | `src/gateway`, `src/monitoring` | Pendente |
| PR-7 | Transversal + `docs/PERFORMANCE.md` | Pendente |

Detalhes de cada entrega: `PROGRESS.md` (seção Robustez PR-n).

## Skips conhecidos (`pytest -rs`)

Captura em 2026-11-23 (**341 passed, 14 skipped**).

| Teste | Motivo |
| :--- | :--- |
| `tests/test_agents.py` (8) | Agentes (Router/Planning/Execution/Validation/Learning) ainda não implementados |
| `tests/test_gateway.py` (3) | Gateway depende de Ollama/PostgreSQL/MQTT — fixtures pendentes |
| `tests/test_rag.py` (3) | RAG depende de embeddings reais — fixtures pendentes |

Saída completa: `/opt/cursor/artifacts/pytest-rs-pr3.txt`