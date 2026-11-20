# Desenvolvimento — YBY SEED

Como rodar e onde tocar código no v1 (PC Hub). Decisões vigentes: [DECISIONS.md](../DECISIONS.md). Mapa de repos: [REPOS.md](REPOS.md).

## Setup

```bash
make setup                            # venv + requirements + requirements-dev
# ou:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # ruff, pytest
ollama pull qwen2.5-coder:3b
cp .env.example .env                  # preencha chaves só no .env local
```

Nunca commite `.env` nem chaves. O template é `.env.example`.

Depois do setup: `make doctor` (ambiente) e `make test` (pytest).

## Comandos CLI

| Comando | O que faz |
|---|---|
| `python yby.py ask "..."` | texto via HybridEngine (Ollama → nuvem se pesado/`--heavy`) |
| `python yby.py run "..."` | porta de segurança → executa se permitido |
| `python yby.py gate "..."` | só decide (run/ask/refuse); não executa |
| `python yby.py note "título" texto da nota...` | grava no vault |
| `python yby.py recall "consulta"` | busca no vault |
| `python yby.py listen` | push-to-talk: Whisper → ask → Piper |
| `python yby.py ask --voice "..."` | mesmo fluxo com prompt opcional |
| `python yby.py hub` | keepalive do hub (Ollama); `--once` para uma checagem |
| `python yby.py agent "..." --script examples/agent_demo_script.json` | loop P0 (demo sem LLM) |
| `python yby.py agent "..." --local` | loop P0 com planner Ollama (só local) |
| `python yby.py evo report --day YYYY-MM-DD` | Evo v0.1: relatório local (offline) |
| `python -m src.evo report --seed-demo --no-ollama` | mesmo fluxo via módulo |
| `python yby.py assist` | sessão PT-BR para tools cadastradas do PC ([ASSIST.md](ASSIST.md)) |

Voz: `pip install -r requirements-voice.txt`, binário Piper no PATH e `YBY_PIPER_MODEL`. Sem isso, `ask` em texto segue; a voz avisa com mensagem clara.

Hub no boot: `bash scripts/install-hub-service.sh --enable`. Detalhe: [PLATFORM.md](PLATFORM.md).

## Variáveis úteis (`.env`)

| Prefixo / chave | Uso |
|---|---|
| `YBY_OLLAMA_*`, `YBY_LOCAL_MODEL` | Ollama do `ask` / hub |
| `YBY_CLOUD_*` / `OPENROUTER_API_KEY` | nuvem primária (OpenRouter free por padrão); só com roteamento pesado/`--heavy` + gate |
| `YBY_GROK_*` / `XAI_API_KEY` | Grok configurável; **não** é chamado automaticamente se OpenRouter falhar (D12, #42) |
| Falha Ollama (caminho local) | **não** dispara nuvem automática (D12 / fase P); ver `HybridEngine._after_local_failure` |
| `YBY_CACHE_*`, `YBY_CACHE_PATH`, `YBY_CLOUD_CONTEXT_MAX_CHARS` | cache TTL (disco em `~/.local/state/yby-seed/response-cache.json`; `YBY_CACHE_PATH=memory` desliga o arquivo) e limite de contexto na nuvem |
| `YBY_OLLAMA_NUM_CTX`, `YBY_OLLAMA_NUM_PREDICT`, `YBY_OLLAMA_THINK` | contexto local (padrão 4096, cabe em 4 GB), teto de tokens (padrão 1024) e thinking do Ollama (padrão omitido no JSON; `sim` envia `think: true`) |
| `YBY_HEAVY_*` | limiares / frases que sobem para nuvem |
| `YBY_VAULT_PATH` | pasta do vault Obsidian; backup: `scripts/backup-vault.sh` ([BACKUP.md](BACKUP.md)) |
| `YBY_VOICE_MAX_SECONDS` | teto da gravação push-to-talk (padrão 120) |
| `YBY_HUB_*` | intervalo/timeout do keepalive |
| `GATEWAY_TOKEN`, `FASTAPI_HOST` | gateway HTTP (fora do caminho do `ask`) |
| `YBY_DATABASE_URL` | Postgres opcional (agentes legados) |

Roteamento do `ask`: `src/engine/routing.py` e `src/engine/config.py`.

## Onde editar

| Objetivo | Pastas |
|---|---|
| Resposta / provedores / roteamento / cache | `src/engine/` |
| Hub keepalive | `src/platform/`, `scripts/install-hub-service.sh` |
| Allowlist e decisão de comando | `src/safety/`, `config/safety-allowlist.txt` |
| Execução após a porta | `src/actions/` |
| Notas / recall | `src/memory/` |
| Código gerado perigoso | `src/security/ast_guard.py` |
| CLI | `src/main.py`, `yby.py` |
| Testes | `tests/` |

**Não mexa** em `src/agents`, `src/rag`, `src/gateway`, `src/core` (legado), etc. a menos que a tarefa seja explicitamente sobre esse módulo. Eles não estão no caminho do `ask`. Ver [src/README.md](../src/README.md).

## LiteLLM (duas configs)

- **Canônica:** `litellm_config.yaml` na raiz (aliases `yby-local`, etc., alinhados a D3/D4).
- **Espelho antigo:** `litellm/config.yaml` — não use como fonte da verdade; preferir a raiz.

O `ask` atual fala com Ollama/nuvem direto via `src/engine`; o proxy LiteLLM é opcional/legado de custo.

## Testes e CI

```bash
make doctor            # Python, arquivos-chave, imports, alvos Make
make lint              # ruff check src tests
make test              # pytest tests -q
make check             # doctor + lint + test
```

O CI em push/`main` e em todo PR roda os mesmos três alvos e falha o check se algum quebrar. Detalhe e Bugbot: [CI.md](CI.md). Não precisa de Docker para o núcleo.

## O que não fazer

- Programar features do YBY em forks (`langgraph`, `llama.cpp`, …).
- Mesclar YBY / yby-core / FRANK_* para dentro deste repo.
- Colocar segredos no repositório.
- Tratar docs longos em `docs/` (arquitetura 7B, mobile, financiamento) como o caminho atual — ver [README do docs](README.md).
