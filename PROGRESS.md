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

## Robustez PR-2 — `src/memory` + `src/rag`

**Objetivo:** dedupe/rate episódios, fila local sqlite3, retry HTTP Mem0, janela de contexto RAG e cache de busca/embeddings.

**Status:** concluída (merge #114).

**Novos módulos:**

- `src/memory/episode_guard.py`, `pending_queue.py`, `remote_store.py`, `episode_pipeline.py`
- `src/rag/context_window.py`, `search_cache.py`
- IoT: `mem0_bridge` reutiliza `EpisodeGuard`

**Testes:** `tests/memory/test_episode_pipeline.py`, `tests/rag/test_context_window.py`

**Próximo:** PR-3 endurecer `src/iot` (flood MQTT).

## Robustez PR-3 — `src/iot`

**Objetivo:** reconexão MQTT com backoff + jitter, validação de payload sem crash, fila anti-flood e dedupe única com `EpisodePipeline`.

**Status:** implementada; PR aberto.

**Correções:**

- `src/iot/reconnect.py` — atraso exponencial (1s, 2s, 4s, 8s…) com jitter.
- `src/iot/message_queue.py` — fila limitada (`IOT_MAX_QUEUE_SIZE`, padrão 100) com drop e log estruturado.
- `src/iot/client.py` — reconexão configurável (`IOT_RECONNECT_MAX_ATTEMPTS`, padrão 5), fila de ingestão.
- `src/iot/handlers.py` — `parse_message_safe()` e log `iot_payload_rejected` (sem corpo da mensagem).
- `src/iot/mem0_bridge.py` — `save_episode_via_pipeline()` (guard uma vez; `apply_guard=False` no pipeline).
- `src/memory/episode_pipeline.py` — flag `apply_guard` / `fingerprint` para evitar dupla filtragem no flush.

**Testes:** `tests/iot/test_mqtt_robustness.py` (+ ajustes em `test_mqtt_client.py`).

**Próximo:** PR-4 voz + visão.

## Correção crítica 1 — Gateway `await` em `insert` (A01)

**Objetivo:** corrigir achado crítico A01 da auditoria (#117).

**Status:** implementada; merge #118.

**Correções:** `process_batch` assíncrono com `await db_client.insert`; worker chama `await process_batch` no event loop.

**Testes:** `tests/gateway/test_process_batch.py` (sucesso só após insert; falha propaga erro).

## Correção crítica 2 — MQTT thread-safe → asyncio.Queue (A02)

**Objetivo:** corrigir achado crítico A02 da auditoria (#117).

**Status:** implementada; merge #119.

**Correções:** `enqueue_mqtt_payload` usa `loop.call_soon_threadsafe`; loop registrado no `userdata` do cliente Paho.

**Testes:** `tests/gateway/test_mqtt_listener_threadsafe.py` (thread Paho, fila cheia, callbacks concorrentes).

## Robustez PR-A — revisão camada 1 (pós #113)

**Objetivo:** segunda passagem em `src/core`, `src/engine`, `src/agent_loop` — confirmar merge #113, atualizar skips, fechar lacunas de exceção no loop.

**Status:** concluída (merge #116).

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

## Camada: estabilização do núcleo básico (ambiente + gates)

**Objetivo:** confirmar o núcleo (instalação, `ask`, safety, memória) com `make check` neste workspace; sem expandir voz/agente/RAG/gateway; sem editar regras Cursor nem diagramas.

**Status:** concluída no ambiente (gates verdes). Smoke real com Ollama **pendente** (sem pull de modelo / sem chamada externa nesta missão).

**Critérios do básico:**

| Critério | Estado | Evidência |
|----------|--------|-----------|
| Instalação + `make doctor` | concluído | `make setup` + doctor PASS |
| Conversa texto (mocks) | concluído | suite pytest (ask/engine/cache/budget) |
| Ações controladas | concluído | `tests/test_safety.py`, `tests/test_actions.py` |
| Memória local (tmp) | concluído | `tests/test_vault.py` |
| Gates locais | concluído | doctor + ruff + pytest |
| Smoke Ollama real | bloqueado / pendente | proibido baixar modelo; não fingido |

**Ambiente:**

- Branch: `main` @ `7866c22`
- Python 3.12.3; `.venv` criado após instalar `python3.12-venv` (ensurepip ausente no VM)
- Só manifests existentes: `requirements.txt` + `requirements-dev.txt` (sem deps novas)

**Arquivos desta fatia:**

- Criado: `.venv/` (gitignored)
- Editado: `PROGRESS.md` (esta nota)
- **Não** alterados: `AGENTS.md`, `.cursor/rules/*`, `docs/diagrams/*`, código de produção

**Evidências (2026-11-24):**

```text
make setup → Setup OK
make check
→ doctor: PASS
→ ruff: All checks passed!
→ pytest: 349 passed, 15 skipped, 10 warnings (14.54s)
.venv/bin/python yby.py --help → comandos ask/run/gate/note/recall listados
```

**Preservado (diff local pré-existente):**

- `AGENTS.md`, `.cursor/rules/yby.mdc`, `.cursor/rules/yby-economy.mdc` (modificados)
- `docs/diagrams/yby-request-flow.{md,html}` (untracked)

**P2 / próximos (não iniciados):**

1. Smoke local: `ollama pull qwen2.5-coder:3b` + `python yby.py ask "..."` na máquina do dono.
2. `yby ask` (texto e `--voice`/`listen`): `HybridEngine.close()` no `finally` (branch `cursor/ask-engine-close-6eec`). Pendente: `yby agent --local`.
3. Warnings FastAPI `on_event` / `datetime.utcnow` no gateway (fora do núcleo `ask`).

## Camada: versionar regras + diagramas + smoke sem Ollama

**Objetivo:** colocar em branch/PR o trabalho local (regras, POC visual, progresso); validar núcleo neste VM Cursor; sem instalar Ollama/modelo sem aprovação extra.

**Status:** branch `cursor/basic-docs-and-progress-6eec` (base `7866c22`). Smoke parcial OK; `ask`+modelo pendente.

**Ambiente desta instalação:**

| Item | Valor |
|------|--------|
| Host | `cursor` (Cloud Agent VM; **não** o PC pessoal) |
| Usuário | `ubuntu` |
| Diretório | `/agent/repos/yby-seed` |
| Python | 3.12.3 + `.venv` (gitignored) |
| Ollama | ausente |

**Como repetir neste VM:**

```bash
make setup          # se .venv ausente
make check
YBY_VAULT_PATH=/tmp/yby-smoke-vault .venv/bin/python yby.py note "smoke" "texto"
YBY_VAULT_PATH=/tmp/yby-smoke-vault .venv/bin/python yby.py recall "teste"
.venv/bin/python yby.py gate "ls"
.venv/bin/python yby.py run "ls"
.venv/bin/python yby.py ask "ping"   # espera falha Ollama clara, sem nuvem
```

**Smoke (2026-11-24, sem Ollama):**

```text
make check → doctor PASS; ruff OK; 349 passed, 15 skipped
help → ask/run/gate/note/recall listados
note → /tmp/yby-smoke-vault/smoke.md
recall "teste" → hit smoke.md
gate ls → run (exit 0); gate "rm -rf /" → refuse (exit 1)
run ls → exit 0
ask "ping" → exit 1; notice: Ollama falhou… Nuvem não é acionada automaticamente (D12)
```

**Skips pytest (HEAD `82f171a`, revalidado nesta sessão):**

| Qtd | Motivo | Bloqueia ask/safety/memory? |
|-----|--------|------------------------------|
| 8 | `tests/test_agents.py` — Router/Planning/Execution/Validation/LearningAgent não implementados | Não (legado agents) |
| 3 | `tests/test_gateway.py` — Ollama/PostgreSQL/MQTT fixtures pendentes | Não (gateway fora do núcleo) |
| 3 | `tests/test_rag.py` — embeddings reais / fixtures pendentes | Não (RAG fora do núcleo) |
| 1 | `tests/vision/test_fusion_client.py` — Pillow não instalado | Não (vision) |

```text
.venv/bin/python -m pytest tests -q -rs
→ 349 passed, 15 skipped, 10 warnings (13.96s); exit 0
```

**CI / merge (PR #123):**

- Doctor, Lint, Test, auto-review, Vercel: verdes em HEAD
- Merge autorizado nesta missão quando CI limpo

**Commits desta branch:**

1. `bec75a7` — `docs(agents): alinhar regras Cursor sem contradições`
2. `2ed9246` — `docs(diagrams): POC visual do fluxo yby ask`
3. `82f171a` — `docs(progress): estabilização, smoke e handoff VM cursor`

**No PC do dono ainda falta:**

1. Clone/pull da branch ou main após merge
2. `make setup` + Ollama + `ollama pull qwen2.5-coder:3b` (~1.9 GB típico)
3. Smoke `yby ask "..."` com modelo local
4. Vault real via `YBY_VAULT_PATH` (não usar o `/tmp` do VM)

**Não iniciado:** systemd hub, Docker, deploy remoto, PR #122 (`close()`). Instalar Ollama neste VM: **não** (pedido: só com aprovação).
