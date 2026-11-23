# Scan de robustez — plano em camadas (pós visão + IoT)

Mapeamento e correções incrementais. Um PR por camada; métricas finais em `docs/PERFORMANCE.md` (PR-7).

| PR | Camada | Status |
| :--- | :--- | :--- |
| **PR-1** | `src/core`, `src/engine`, `src/agent_loop` | Em review |
| PR-2 | `src/memory`, `src/rag` | Pendente |
| PR-3 | `src/iot` | Pendente |
| PR-4 | `src/voice`, `src/vision` | Pendente |
| PR-5 | `src/safety`, `src/security` | Pendente |
| PR-6 | `src/gateway`, `src/monitoring` | Pendente |
| PR-7 | Transversal + `docs/PERFORMANCE.md` | Pendente |

Detalhes de cada entrega: `PROGRESS.md` (seção Robustez PR-n).

## Skips conhecidos (`pytest -rs`)

Captura 2026-11-23 (pós PR-CRIT-1): **326 passed**, **14 skipped** — 8× `tests/test_agents.py` (agentes não implementados); 3× `tests/test_gateway.py` (fixtures legado); 3× `tests/test_rag.py` (embeddings reais).