# PROGRESS — YBY SEED

Registro incremental de camadas. Harness kit (`CONTRACT.md`, `config/agent/state.json`) na branch PR #105; camadas #106 e #107 integradas via `main`.

## Camada: harness engineering kit (docs only)

**Objetivo:** contrato de tarefa, memória externa e estado legível por máquina para agentes (harness engineering).

**Status:** concluída (commit `d9e07dc`, PR #105).

**Arquivos:**

- Criado: `CONTRACT.md`
- Criado: `config/agent/state.json`
- Criado: `PROGRESS.md` (template de sessão + este registro)
- Editado: `AGENTS.md` (workflow harness, regras YBY SEED preservadas)

**Evidências (2026-11-23, fatia harness):**

```text
branch: docs/agent-harness-kit @ d9e07dc
git show d9e07dc --stat
→ AGENTS.md, CONTRACT.md, PROGRESS.md, config/agent/state.json
```

## Camada concluída: contrato CLI do `yby agent`

**Objetivo:** testes Click offline para `yby agent` + exemplo copy-paste em `docs/DEV.md`. Sem alterar runtime (`src/main.py`, `src/agent_loop/`, engine).

**Status:** concluída (sensores verdes, PR #106 → `main`).

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
- `CONTRACT.md` / `config/agent/state.json` entram com PR #105 (fora do escopo do #106).

**Próximo passo:** uma camada pequena — alinhar docstring de `src/engine/routing.py` (L17–18) com D12 / `_after_local_failure`, ou integrar `ask --agent` (só após decisão humana).

## Camada: P0-D12-ROUTING-DOC (docs only)

**Objetivo:** docstring de `routing.py` alinhada a D12 — falha Ollama **não** auto-cai para nuvem.

**Status:** implementada (PR #106 → `main`).

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

**Decisões:** só docstring/`__init__`; sem mudança de comportamento.

## Camada: P1-DECISIONS-D3 (docs only)

**Objetivo:** alinhar D3 e `MODEL_CARD.md` ao runtime v1 — OpenRouter como destino padrão do caminho nuvem; sem cascade automático OpenRouter→Grok.

**Status:** concluída (commit base `578d221`, PR #107 → `main`).

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

**Status:** concluída (commit base `d349e0d`, PR #107 → `main`).

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

**Status:** consolidada em `main` (PR #107).

**Evidências (2026-11-23, pós-merge local com `origin/main` / PR #106):**

```text
branch: docs/decisions-cloud-routing @ origin/main
make check
→ doctor: PASS; ruff: All checks passed!; pytest: 301 passed, 14 skipped
git diff origin/main --stat → DECISIONS.md, MODEL_CARD.md, PROGRESS.md apenas
```

**Próximo passo:** revisão humana do PR #105 (harness + `PROGRESS` unificado); merge após CI verde.

---

## Modelo harness — memória de sessão do agente

> Este bloco é a memória externa do agente (template PR #105).  
> Se uma informação não está aqui, ela não deve ser considerada conhecida na próxima sessão.

### Estado atual

- **Tarefa ativa:**
- **Fase:**
- **Status:** `NOT_STARTED | IN_PROGRESS | BLOCKED | DONE | FAILED`
- **Última atualização:**

### Objetivo atual

Descreva brevemente o que precisa ser entregue.

```text
Exemplo: implementar endpoint /health com teste e documentação.
```

### Etapas

| ID | Etapa | Status | Evidência | Observação |
|---|---|---|---|---|
| 1 | Ler contrato e documentos relevantes | `PENDING` |  |  |
| 2 | Planejar alterações | `PENDING` |  |  |
| 3 | Implementar | `PENDING` |  |  |
| 4 | Executar testes | `PENDING` |  |  |
| 5 | Executar lint/build | `PENDING` |  |  |
| 6 | Atualizar documentação | `PENDING` |  |  |
| 7 | Criar commit | `PENDING` |  |  |
| 8 | Relatório final | `PENDING` |  |  |

### Decisões registradas

| Data | Decisão | Motivo | Impacto |
|---|---|---|---|
|  |  |  |  |

### Caminhos já testados e descartados

| Tentativa | Resultado | Motivo do descarte |
|---|---|---|
|  |  |  |

### Bloqueios

| Item | Motivo | Ação necessária | Responsável |
|---|---|---|---|
|  |  |  |  |

### Log de sensores

| Data | Sensor | Comando | Resultado | Evidência |
|---|---|---|---|---|
|  |  |  |  |  |

### Próximo passo (sessão)

```text
Exemplo: implementar teste unitário do endpoint /health.
```