# Scan de robustez — plano em camadas (pós visão + IoT)

Mapeamento e correções incrementais. Um PR por camada; métricas finais em `docs/PERFORMANCE.md` (PR-7).

| PR | Camada | Status |
| :--- | :--- | :--- |
| **PR-1** | `src/core`, `src/engine`, `src/agent_loop` | Concluído (#113) |
| **PR-A** | Revisão da camada 1 (pós-merge #113) | Concluído (#116) |
| **PR-2** | `src/memory`, `src/rag` | Concluído (#114) |
| **PR-3** | `src/iot` | Concluído (#115) |
| PR-4 | `src/voice`, `src/vision` | Pendente |
| PR-5 | `src/safety`, `src/security` | Pendente |
| PR-6 | `src/gateway`, `src/monitoring` | Pendente |
| PR-7 | Transversal + `docs/PERFORMANCE.md` | Pendente |

Detalhes de cada entrega: [HISTORY.md](HISTORY.md) (seção Robustez PR-n / PR-A).

## Skips conhecidos (`pytest -rs`)

Captura 2026-11-26 (`main` @ `36de739` + auditoria de skips): **728 passed**, **1 skipped**.

| Área | Qtd | Motivo | Classe |
| :--- | ---: | :--- | :--- |
| `tests/vision/test_fusion_client.py::test_fusion_client_analyze_with_mocks` | 1 | Pillow ausente — extra opcional em `requirements-vision.txt`, não instalado no CI/`make setup`; visão fora do `ask` | Legítimo |

Removidos na auditoria de 2026-11-26: 14 placeholders sem asserts em `tests/test_agents.py` (8), `tests/test_gateway.py` (3) e `tests/test_rag.py` (3). Os motivos declarados ("não implementado", "fixtures pendentes") estavam desatualizados: as classes existem e o comportamento tem testes reais (`tests/test_*_agent.py`, `tests/test_vault.py`, `tests/gateway/`, `tests/test_gateway_auth.py`, `tests/rag/`, `tests/test_deep_scan_regressions.py`).

## PR-A — checklist (core / engine / agent_loop)

| Item | Estado |
| :--- | :--- |
| HTTP retry/backoff (`_post_with_retry`, 408/429/502/503/504) | OK (#113) |
| `HybridEngine.close()` / provedores | OK (#113) |
| `tool_timeout_seconds` no `ControlledAgentLoop` | OK (#113) |
| `OllamaClientError` + timeouts no legado | OK (#113) |
| Exceção não prevista em tool → `status=error` (sem crash) | Corrigido (PR-A) |
| `yby ask` / `yby agent --local` sem `close()` explícito no CLI | Follow-up (fora de `src/agent_loop`) |
