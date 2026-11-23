# PROGRESS — YBY SEED

Registro incremental de camadas. Sem `CONTRACT.md` / `config/agent/state.json` neste repo ainda.

## Camada concluída: contrato CLI do `yby agent`

**Objetivo:** testes Click offline para `yby agent` + exemplo copy-paste em `docs/DEV.md`. Sem alterar runtime (`src/main.py`, `src/agent_loop/`, engine).

**Status:** concluída (sensores verdes).

**Arquivos:**

- Criado: `tests/test_agent_cli.py` (5 testes)
- Criado: `PROGRESS.md`
- Editado: `docs/DEV.md` (bloco copy-paste)

**Evidências (2026-11-23):**

```text
PYTHONPATH=. python3 -m pytest tests/test_agent_cli.py -q
→ 5 passed

make check
→ doctor: PASS
→ ruff: All checks passed!
→ pytest: 301 passed, 14 skipped
```

**Decisões:**

- JSON “inválido” no contrato = objeto `{}` (não-array); exit `1` explícito em `agent_cmd`.
- Sem `--local` nos testes (evita Ollama/rede).
- `config/agent/state.json` e `CONTRACT.md` não criados (fora do necessário nesta camada).

**Próximo passo:** uma camada pequena — alinhar docstring de `src/engine/routing.py` (L17–18) com D12 / `_after_local_failure`, ou integrar `ask --agent` (só após decisão humana).
