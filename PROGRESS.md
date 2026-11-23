# PROGRESS — YBY SEED

Registro incremental de camadas. Sem `CONTRACT.md` / `config/agent/state.json` neste repo ainda.

**Branch consolidada:** `docs/decisions-cloud-routing` (D3 + D12 + MODEL_CARD). Não mistura com PR #106 nem PR #105.

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

**Evidências (2026-11-23, pós-merge local):**

```text
branch: docs/decisions-cloud-routing @ origin/main
make check
→ doctor: PASS; ruff: All checks passed!; pytest: 296 passed, 14 skipped
git diff origin/main --stat → DECISIONS.md, MODEL_CARD.md, PROGRESS.md apenas
```

**Próximo passo:** revisão humana do diff; push/autorização para abrir PR docs; depois `P1-ARCHITECTURE-BANNER`.