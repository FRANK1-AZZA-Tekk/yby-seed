# Desenvolvimento — YBY SEED

Como rodar e onde tocar código no v1 (PC Hub). Decisões vigentes: [DECISIONS.md](../DECISIONS.md). Mapa de repos: [REPOS.md](REPOS.md).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # ruff, pytest
ollama pull qwen2.5-coder:3b
cp .env.example .env                  # preencha chaves só no .env local
```

Nunca commite `.env` nem chaves. O template é `.env.example`.

## Comandos CLI

| Comando | O que faz |
|---|---|
| `python yby.py ask "..."` | texto via HybridEngine (Ollama → nuvem se pesado/`--heavy`; padrão `local_only`) |
| `python yby.py ask --explain "..."` | envelope professor PT-BR; pedido de criação aponta `brief start` (ask não abre brief) |
| `python yby.py --help` | epílogo: brief→plan→scaffold, gate/run, nuvem off por padrão |
| `python yby.py run "..."` | porta de segurança → executa se permitido (refuse/ask negado: envelope); teto de timeout/saída; bloqueia cwd/alvo de scaffold |
| `python yby.py gate "..."` | só decide (run/ask/refuse) com envelope; não executa |
| `python yby.py note "título" texto da nota...` | grava no vault (atualiza índice) |
| `python yby.py recall "consulta"` | busca no índice local |
| `python yby.py recall --fresh "…"` / `reindex` | reindex incremental por content-hash (Syncthing/edições externas) |
| `python yby.py prefs list/get/set …` | preferências no vault; chaves sensíveis exigem `--consent` |
| `python yby.py research "…" [--consent]` | pesquisa com gate de consentimento; HTTP fake (sem busca real) |
| `python yby.py devices schema/validate/simulate` | contrato `yby-device/v1` + bus fake (sem firmware/MQTT) |
| `python yby.py backup create/list/restore …` | tar.gz local do vault + logs redigidos (sem nuvem; restore em pasta alvo) |
| `python yby.py usage` / `usage tail` | resumo do `cloud_usage.jsonl` + orçamento mensal (local) |
| `python yby.py learn log/report …` | aprendizado diário em JSONL + relatório (sem auto-merge em docs) |
| `python yby.py brief start "ideia"` | inicia YBY-BRIEF (entrevista; sem código) |
| `python yby.py brief answer <id> <campo> ...` | preenche campo / retoma |
| `python yby.py brief show <id> [--cloud-safe]` | mostra brief |
| `python yby.py brief propose <id>` | proposta só se completo (não é plano) |
| `python yby.py plan from-brief <brief_id>` | gera plano validado (não executa) |
| `python yby.py plan show/validate/revise …` | inspeciona / revalida / nova versão |
| `python yby.py cursor-fake simulate <plan_id>` | dry-run de plano `validated` (sem MCP / sem escrita) |
| `python yby.py scaffold propose <plan_id> <dir> --name …` | propõe scaffold Python CLI (manifesto) |
| `python yby.py scaffold apply <proposal.json>` | aplica após aprovação (sem pip install) |
| `python yby.py scaffold revert <dir>` | remove arquivos do manifesto |
| `python yby.py scaffold validate <proposal.json>` | validação estática (sintaxe/testes/segredos) |
| `python yby.py scaffold test-generated <dir>` | **sempre bloqueado** no v1 (sem sandbox OS) |
| `python yby.py listen` | push-to-talk: Whisper → ask → Piper |
| `python yby.py ask --voice "..."` | mesmo fluxo com prompt opcional |
| `python yby.py hub` | keepalive do hub (Ollama); `--once` para uma checagem |
| `python yby.py agent "..." --script examples/agent_demo_script.json` | loop P0 (demo sem LLM) |
| `python yby.py agent "..." --local` | loop P0 com planner Ollama (só local) |

Voz: `pip install -r requirements-voice.txt`, binário Piper no PATH e `YBY_PIPER_MODEL`. Sem isso, `ask` em texto segue; a voz avisa com mensagem clara.

Hub no boot: `bash scripts/install-hub-service.sh --enable`. Detalhe: [PLATFORM.md](PLATFORM.md).

## Variáveis úteis (`.env`)

| Prefixo / chave | Uso |
|---|---|
| `YBY_OLLAMA_*`, `YBY_LOCAL_MODEL` | Ollama do `ask` / hub |
| `YBY_CLOUD_*` / `OPENROUTER_API_KEY` | destino único de nuvem (OpenRouter free por padrão; sem cascade Grok) |
| `YBY_CLOUD_MODE` | `local_only` (padrão, nuvem off) ou `ask` (nuvem com confirmação); outros valores falham |
| `YBY_CACHE_*`, `YBY_CLOUD_CONTEXT_MAX_CHARS` | cache TTL e limite de contexto na nuvem |
| `YBY_HEAVY_*` | limiares / frases que sobem para nuvem |
| `YBY_VAULT_PATH` | pasta do vault Obsidian |
| `YBY_BACKUP_DIR`, `YBY_BACKUP_KEEP` | pasta dos archives (padrão `backups/yby`) e retenção (padrão 7) |
| `YBY_RUN_TIMEOUT_MAX`, `YBY_RUN_OUTPUT_MAX_BYTES` | teto do `yby run` (padrão 120s / 1 MiB) |
| `YBY_LEARN_LOG_PATH` | JSONL de aprendizado (padrão `logs/learn.jsonl`) |
| `YBY_HUB_*` | intervalo/timeout do keepalive |
| `GATEWAY_TOKEN`, `FASTAPI_HOST` | gateway HTTP (fora do caminho do `ask`) |
| `YBY_DATABASE_URL` | Postgres opcional (agentes legados) |

Roteamento do `ask`: `src/engine/routing.py` e `src/engine/config.py`.

## Onde editar

| Objetivo | Pastas |
|---|---|
| Resposta / provedores / roteamento / cache | `src/engine/` |
| Envelope professor (`--explain` / gate) | `src/conversation/` |
| Entrevista YBY-BRIEF | `src/brief/` |
| Plano verificável | `src/plan/` |
| Scaffold de artefatos | `src/artifacts/` |
| Hub keepalive | `src/platform/`, `scripts/install-hub-service.sh` |
| Allowlist e decisão de comando | `src/safety/`, `config/safety-allowlist.txt` |
| Execução após a porta | `src/actions/` (limites em `limits.py`) |
| Notas / recall / prefs | `src/memory/` |
| Backup local vault+logs | `src/backup/` |
| Observabilidade usage CLI | `src/obs/` |
| Cursor fake (dry-run de plano) | `src/cursor_fake/` |
| Aprendizado diário | `src/learn/` |
| Pesquisa consentida (fake HTTP) | `src/research/` |
| Contratos dispositivos (fake) | `src/devices/` |
| Código gerado perigoso | `src/security/ast_guard.py` |
| CLI | `src/main.py`, `yby.py` |
| Testes | `tests/` |

**Não mexa** em `src/agents`, `src/rag`, `src/gateway`, `src/core` (legado), etc. a menos que a tarefa seja explicitamente sobre esse módulo. Eles não estão no caminho do `ask`. Ver [src/README.md](../src/README.md).

## LiteLLM (duas configs)

- **Canônica:** `litellm_config.yaml` na raiz (aliases `yby-local`, etc., alinhados a D3/D4).
- **Espelho antigo:** `litellm/config.yaml` — não use como fonte da verdade; preferir a raiz.

O `ask` atual fala com Ollama/nuvem direto via `src/engine`; o proxy LiteLLM é opcional/legado de custo.

## Testes

```bash
ruff check src tests   # igual ao CI
pytest -q
# ou: make check
```

O CI roda o mesmo em push/PR. Não precisa de Docker para o núcleo.

## O que não fazer

- Programar features do YBY em forks (`langgraph`, `llama.cpp`, …).
- Mesclar YBY / yby-core / FRANK_* para dentro deste repo.
- Colocar segredos no repositório.
- Tratar docs longos em `docs/` (arquitetura 7B, mobile, financiamento) como o caminho atual — ver [README do docs](README.md).
