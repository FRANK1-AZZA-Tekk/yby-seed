# PROGRESS — YBY SEED

Estado operacional atual. Histórico de camadas concluídas: [docs/HISTORY.md](docs/HISTORY.md). Sem `CONTRACT.md` / `config/agent/state.json` neste repo ainda.

## Retomada atual

**Atualizado:** 2026-11-26 (avaliação offline pt-BR; VM `/agent/repos/yby-seed`).

| Campo | Estado |
|-------|--------|
| **Tarefa desta linha** | **Avaliação offline pt-BR** — conjunto [evals/ptbr_basico.json](evals/ptbr_basico.json) (6 casos: resposta direta, explicação técnica, tool segura, entrada ambígua, entrada inválida, recusa segura; ficha de admissão no próprio JSON) + executor `scripts/eval_offline.py` (fakes, relógio simulado, sem rede/nuvem/Ollama/`.env`) + `tests/test_eval_offline.py`; seção em [docs/DEV.md](docs/DEV.md#avaliação-offline-pt-br). Mede o pipeline, não o modelo. `src/evaluation` (congelado), produto, D12, route, cache, orçamento e permissões inalterados. Branch `cursor/eval-offline-ptbr-0bef`. |
| **`main` remoto (base)** | `70b5447822dd1080f5d600666df3b6db9e23a07c` (idempotência de tools, PR #159). |
| **Validação local** | `scripts/eval_offline.py` **6/6 ok**, nuvem 0, 1 tool, latência simulada 1505 ms; `test_eval_offline` **29 passed**; `make check` exit 0 (doctor PASS, ruff OK, **803 passed, 1 skipped**); `git diff --check` OK. CI: consultar no SHA final do PR. |
| **WIP / stash** | OID `1688e8117cc7669a54f95c9d38b479c82cdc2dfa` **não existe nesta VM** (`git stash list` vazio); nenhum comando de stash executado. Se existir em outra máquina, segue preservado lá. |
| **Pendência real** | (1) Aceite do núcleo no PC Hub: smokes Ollama e OpenRouter do [checklist](#checklist-de-aceite-do-núcleo-consolidado), não executados nesta VM. (2) Lacunas de cobertura de `src/gateway` e `src/rag` (item A11 de [AUDIT-REPORT.md](docs/AUDIT-REPORT.md)), fora do núcleo. (3) Backlog P0 do [ROADMAP.md](ROADMAP.md) ("loop controlado", "contratos de tools") parece implementado em `src/agent_loop`, mas não foi conferido contra os critérios de aceite. (4) Decisão do dono sobre as recomendações de [LAYER_ADMISSION.md](docs/LAYER_ADMISSION.md#6-classificação-das-camadas-existentes) (congelar/arquivar). (5) Registro persistente de operações e integração no `ToolRegistry`, só junto da primeira tool mutável (ficha própria). (6) Avaliação: modo local real (mesmo conjunto contra Ollama no PC Hub, latência real) exige aprovação; classificar a nova frente `evals/` em LAYER_ADMISSION. |
| **Próxima sugerida** | Smokes no PC Hub via agente aberto na própria máquina; ou canal local de aprovação na CLI para tools `manual`; ou Glass G1b; ou OpenCode O1 — todas exigem aprovação. |

*Não é fonte de autorização; regras em `AGENTS.md`.*

## Checklist de aceite do núcleo (consolidado)

**Base documentada:** `main` @ `69e841e` (PR #155). Itens verificados introduzidos em #123–#127; camadas posteriores no [índice do histórico](docs/HISTORY.md#índice-de-camadas-sem-seção-própria).

### Verificado (sem provedor real)

| Item | Evidência |
|------|-----------|
| Gates | `make check`: doctor + ruff + pytest (última referência VM: **728 passed**, 1 skipped após #155; ver [ROBUSTNESS-SCAN](docs/ROBUSTNESS-SCAN.md#skips-conhecidos-pytest--rs)) |
| CLI offline | `note`/`recall`/`gate`/`run`; `ask` sem Ollama → exit 1 + aviso D12 (não é aceite Ollama) |
| Motor / HTTP lifecycle | `yby ask` → `HybridEngine.close()` (#125); `yby agent --local` → `OllamaProvider.close()` (#126) |
| Nuvem (código) | `max_tokens` no POST + env `YBY_CLOUD_MAX_OUTPUT_TOKENS` (padrão 512, #127); cache cloud inclui o limite na chave |
| OpenRouter (config) | Template `.env.example` + secção em `docs/DEV.md` — **sem** chamada real neste repositório/VM |
| Núcleo **não** fechado | Dois smokes no PC abaixo |

### Pendente — smoke 1: Ollama (PC)

| | |
|---|---|
| Onde | PC Hub (não VM Cursor) |
| Pré-requisitos | `make setup`; `make check`; Ollama ativo; `ollama pull qwen2.5-coder:3b` |
| Comando | `python yby.py ask "Em uma frase: o que é uma lista ligada?"` |
| Aceite | `exit 0`; stderr `modelo: local qwen2.5-coder:3b` (ou `YBY_LOCAL_MODEL`); resposta em stdout |
| Rejeitar como aceite | Falha D12 / `provider none` — comportamento esperado **sem** Ollama, já validado na VM |

### Pendente — smoke 2: OpenRouter (PC; aprovação humana)

| | |
|---|---|
| Onde | PC Hub; chave só no `.env` local |
| Pré-requisitos | Chave configurada; TTY; `YBY_CLOUD_REQUIRE_CONFIRM=1`; aprovação explícita de gasto |
| Comando | `YBY_CACHE_PATH=memory python yby.py ask --heavy "Responda apenas com a palavra OK."` → confirmar `s` |
| Aceite (CLI) | `exit 0`; `modelo: cloud …` + `heavy_flag`; sem degradação local mascarando o provedor |
| Aceite (log) | JSONL: `cloud_requested` → `cloud_confirmed` → `cloud_completed`; `provider` **openrouter** ou **cloud**, não só `cache` |
| Não confundir | `YBY_CLOUD_MAX_OUTPUT_TOKENS` = teto HTTP; campos `*_tokens_estimate` no JSONL = heurística `len/4`; fatura = painel OpenRouter |
| Corroboração | Atividade no dashboard OpenRouter (sem expor chave ou conteúdo de prompt) |

Roteiro detalhado: `docs/DEV.md` (Smokes de aceite).
