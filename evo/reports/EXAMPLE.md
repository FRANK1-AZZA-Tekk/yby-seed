# Evo report — 2026-11-18

_Generated at 2026-11-18T16:03:36+00:00 (local Evo v0.1). Offline. No automatic code changes._

## Day summary

- **Day:** 2026-11-18
- **Events:** 7
- **By kind:** cloud_call=1, command_run=1, error=1, skill_use=1, task_completed=1, test_result=1, user_feedback=1
- **By severity:** error=1, info=5, warn=1
- **Sources:** agent=1, cli=1, cursor=1, engine=1, logs/cloud_usage.jsonl=1, pytest=1, user=1
- **Analyzer:** heuristic fallback (local)

## Problems

- Ollama indisponível em http://127.0.0.1:11434

## Evidence

- [2026-11-18T10:00:00+00:00] command_run: yby gate "ls" → run
- [2026-11-18T11:00:00+00:00] test_result: pytest tests/test_evo.py — 8 passed
- [2026-11-18T12:00:00+00:00] error: Ollama indisponível em http://127.0.0.1:11434
- [2026-11-18T13:00:00+00:00] task_completed: docs: atualizar README do evo
- [2026-11-18T14:00:00+00:00] user_feedback: relatório útil; falta priorizar flaky tests
- [2026-11-18T15:00:00+00:00] skill_use: skill walkthrough-artifacts
- [2026-11-18T16:00:00+00:00] cloud_call: cloud cancelled: openrouter/free ask

## Hypotheses

- **Instabilidade do Ollama local** (confidence 0.6): Eventos de erro mencionam Ollama ou provider local.
- **Uso de nuvem registado localmente** (confidence 0.5): JSONL/eventos cloud_call presentes (só leitura).

## Prioritized proposals

1. **P1 — Verificar hub/keepalive e `ollama list`**: Reduz falhas de ask/agent --local sem sair do offline.
1. **P2 — Rever confirmações D12 e orçamento**: Cloud calls são evidência local; Evo não chama nuvem.

## Risks

- Relatório sem LLM: hipóteses heurísticas apenas.
- Evo v0.1 não altera código automaticamente.

## Next steps

- Rodar `python yby.py hub --once` e re-gerar o relatório.

---

Evo v0.1 does **not** apply patches, promote Night Watch, or call cloud APIs.
