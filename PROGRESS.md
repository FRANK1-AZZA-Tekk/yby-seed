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

## Camada: P1-DECISIONS-D3 (docs only)

**Objetivo:** alinhar D3 e `MODEL_CARD.md` ao runtime v1 — OpenRouter como destino padrão do caminho nuvem; sem cascade automático OpenRouter→Grok.

**Status:** concluída (commit base `578d221`).

**Arquivos:**

- Editado: `DECISIONS.md` (seção D3)
- Editado: `MODEL_CARD.md` (linhas 86, 112, 145)

**Fora de escopo:** `src/`, testes, D12 (harmonização em fatia seguinte na mesma branch), Makefile, deps, deploy.

**Evidências (2026-11-23, fatia D3):**

```text
branch: docs/decisions-d3-openrouter @ origin/main
make check
→ doctor: PASS
→ ruff: All checks passed!
→ pytest: 296 passed, 14 skipped (sem test_agent_cli.py — só em PR #106)
git diff --stat
→ DECISIONS.md, MODEL_CARD.md, PROGRESS.md apenas
```

## Camada: P1-DECISIONS-D12-HARMONIZATION (docs only)

**Objetivo:** harmonizar regras de D12 com o roteamento v1 (alinhado a D3 revisado), sem reescrever D3 nem alterar código.

**Status:** concluída (commit base `d349e0d`).

**Arquivos:**

- Editado: `DECISIONS.md` (somente bullets de Regras em D12)

**Fora de escopo:** D3 (já revisado na fatia anterior), `MODEL_CARD.md`, `src/`, testes.

**Evidências (2026-11-23, fatia D12):**

```text
branch: docs/decisions-d12-harmonization @ origin/main
make check
→ doctor: PASS; ruff: All checks passed!; pytest: 296 passed, 14 skipped
git diff --stat → DECISIONS.md, PROGRESS.md apenas
```

## Consolidação P1 — roteamento de nuvem

**Status:** consolidada nesta branch.

**Evidências (2026-11-23, pós-merge local com `origin/main` / PR #106):**

```text
branch: docs/decisions-cloud-routing @ origin/main
make check
→ doctor: PASS; ruff: All checks passed!; pytest: 301 passed, 14 skipped
git diff origin/main --stat → DECISIONS.md, MODEL_CARD.md, PROGRESS.md apenas
```

**Próximo passo:** revisão humana do diff; push/autorização para abrir PR docs; depois `P1-ARCHITECTURE-BANNER`.

## Robustez PR-1 — `src/core` + `src/engine` + `src/agent_loop`

**Objetivo:** scan profundo (issue robustez) — camada 1 de 7: retry/backoff HTTP, shutdown de sessões, timeout por tool no loop, erros explícitos no `OllamaClient` legado.

**Status:** concluída (#113 em `main`).

**Correções:**

- `src/engine/providers.py` — `_post_with_retry` (3 tentativas, backoff + 408/429/502/503/504); `close()` em Ollama/Cloud/CascadingCloud.
- `src/engine/hybrid.py` — `HybridEngine.close()`.
- `src/agent_loop/loop.py` — `tool_timeout_seconds` (padrão 30s) com `ThreadPoolExecutor`.
- `src/core/ollama_client.py` — `OllamaClientError`, timeouts, `raise_for_status`, `close()` (não retorna string vazia em falha de rede).

**Testes novos:** `test_ollama_client.py`, `test_robustness_pr1.py`, + provider 503, agent loop timeout.

**Próximo passo (fila):** PR-2 `src/memory` + `src/rag`; depois PR-3 `src/iot`, etc. (`docs/PERFORMANCE.md` na PR-7).

## Robustez PR-A — revisão camada 1 (pós #113)

**Objetivo:** segunda passagem em `src/core`, `src/engine`, `src/agent_loop` — confirmar merge #113, atualizar skips, fechar lacunas de exceção no loop.

**Status:** em review (`cursor/robustness-pr-a-core-0543`).

**Auditoria (resumo):**

- Retry/backoff, timeouts de provedor, `HybridEngine.close()`, tool timeout: conforme #113 (coberto por testes existentes).
- Lacuna: exceção genérica em handler de tool propagava e derrubava o CLI — tratada como `status=error`.
- Follow-up documentado: `yby ask` / `yby agent --local` não chamam `close()` no engine/provider (escopo `src/main.py`).

**Correções PR-A:**

- `src/agent_loop/loop.py` — captura `Exception` em execução de tool (preserva `KeyboardInterrupt` / `SystemExit`).

**Testes novos:** `tests/test_robustness_pr_a.py` (tool RuntimeError, `CascadingCloudProvider.close`, chat OllamaClient rede, close idempotente).

**Evidências (2026-11-23):**

```text
PYTHONPATH=. python3 -m pytest -rs → 328 passed, 14 skipped
PYTHONPATH=. python3 -m pytest -q → 328 passed, 14 skipped
PYTHONPATH=. python3 -m ruff check src/agent_loop/loop.py tests/test_robustness_pr_a.py
→ All checks passed!
make check → doctor FAIL (venv sem ensurepip neste VM); pytest/ruff OK via python3 -m
```