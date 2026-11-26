# PROGRESS — YBY SEED

Estado operacional atual. Histórico de camadas concluídas: [docs/HISTORY.md](docs/HISTORY.md). Sem `CONTRACT.md` / `config/agent/state.json` neste repo ainda.

## Retomada atual

**Atualizado:** 2026-11-26 (política de ações: lacuna j; VM `/agent/repos/yby-seed`).

| Campo | Estado |
|-------|--------|
| **Tarefa desta linha** | **Política de ações do agente** — já em `main` desde PR #153 (`ed2462a`): `config/agent-policy.yaml` + `src/safety/agent_policy.py`, aplicada em `ToolRegistry.authorize` → `AuthorizedCall` → `execute`; itens a–i cobertos por `tests/test_agent_policy.py`. Lacuna fechada nesta rodada: item j com 4 testes offline (route, cache, orçamento e ambiente inalterados pelo uso da política). Sem código de produto. Branch `cursor/policy-gap-j-0bef`. |
| **`main` remoto (base)** | `dbf3ce3f91a8e4c0b4b633be3209232640fe9e10` (consolidação do estado operacional, PR #156). |
| **Validação local** | Direcionados (`test_agent_policy`, `test_engine`, `test_route_cli`, `test_budget`, `test_cache_context`) **114 passed**; `make check` exit 0 (doctor PASS, ruff OK, **732 passed, 1 skipped**); `git diff --check` OK. CI: consultar no SHA final do PR. |
| **PR #157** (admissão de camadas) | Merge autorizado pelo dono, **não feito**: no SHA `e25e87b`, o job Doctor do run `pull_request` 45860018498 ficou preso em `Checkout` (o Doctor do run `push` passou). Merge só com todos os checks verdes. |
| **WIP / stash** | OID `1688e8117cc7669a54f95c9d38b479c82cdc2dfa` **não existe nesta VM** (`git stash list` vazio); nenhum comando de stash executado. Se existir em outra máquina, segue preservado lá. |
| **Pendência real** | (1) Aceite do núcleo no PC Hub: smokes Ollama e OpenRouter do [checklist](#checklist-de-aceite-do-núcleo-consolidado), não executados nesta VM. (2) Lacunas de cobertura de `src/gateway` e `src/rag` (item A11 de [AUDIT-REPORT.md](docs/AUDIT-REPORT.md)), fora do núcleo. (3) Backlog P0 do [ROADMAP.md](ROADMAP.md) ("loop controlado", "contratos de tools") parece implementado em `src/agent_loop`, mas não foi conferido contra os critérios de aceite. |
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
