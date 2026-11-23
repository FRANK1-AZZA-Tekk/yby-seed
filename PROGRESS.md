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

## Camada: P0-D12-ROUTING-DOC (docs only)

**Objetivo:** docstring de `routing.py` alinhada a D12 — falha Ollama **não** auto-cai para nuvem.

**Status:** implementada; aguarda review humano (sem commit).

**Arquivos:**

- Editado: `src/engine/routing.py` (docstring L17–19)
- Editado: `src/engine/__init__.py` (one-liner sem “fallback”)
- Editado: `PROGRESS.md` (esta nota)

**Evidências (baseline pré-edit + pós-edit, 2026-11-23):**

```text
branch: cursor/agent-cli-contract-bcee @ 281afb9
PYTHONPATH=. python3 -m pytest tests/test_engine.py -k ollama_fora -q
→ 3 passed, 25 deselected (exit 0)
make check
→ doctor: PASS; ruff: All checks passed!; 301 passed, 14 skipped (exit 0)
```

**Decisões:** só docstring/`__init__`; sem mudança de comportamento; sem commit/push.
