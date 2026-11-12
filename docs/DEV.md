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
| `python yby.py ask "..."` | texto via HybridEngine (Ollama → nuvem se pesado/`--heavy`) |
| `python yby.py run "..."` | porta de segurança → executa se permitido |
| `python yby.py gate "..."` | só decide (run/ask/refuse); não executa |
| `python yby.py note "título" texto da nota...` | grava no vault |
| `python yby.py recall "consulta"` | busca no vault |
| `python yby.py listen` | push-to-talk: Whisper → ask → Piper |
| `python yby.py ask --voice "..."` | mesmo fluxo com prompt opcional |
| `python yby.py hub` | keepalive do hub (Ollama); `--once` para uma checagem |

Voz: `pip install -r requirements-voice.txt`, binário Piper no PATH e `YBY_PIPER_MODEL`. Sem isso, `ask` em texto segue; a voz avisa com mensagem clara.

Hub no boot: `bash scripts/install-hub-service.sh --enable`. Detalhe: [PLATFORM.md](PLATFORM.md).

## Variáveis úteis (`.env`)

| Prefixo / chave | Uso |
|---|---|
| `YBY_OLLAMA_*`, `YBY_LOCAL_MODEL` | Ollama do `ask` / hub |
| `YBY_CLOUD_*` / `OPENROUTER_API_KEY` | nuvem primária (OpenRouter free por padrão) |
| `YBY_GROK_*` / `XAI_API_KEY` | fallback Grok se OpenRouter falhar/sem chave |
| `YBY_CACHE_*`, `YBY_CLOUD_CONTEXT_MAX_CHARS` | cache TTL e limite de contexto na nuvem |
| `YBY_HEAVY_*` | limiares / frases que sobem para nuvem |
| `YBY_VAULT_PATH` | pasta do vault Obsidian |
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

## LiteLLM (Docker)

- **Canônica:** `config/litellm_config.yaml` (cache Redis, `max_budget: 3.50`, `30d`).
- Subir stack: `make up` · API seed: `make api` · testes: `make test`.

O CLI legado (`yby.py ask`) ainda usa `src/engine/` direto; o núcleo **Vibe Coding** usa LiteLLM em `src/yby_seed/`.

## API HTTP (`/v1/seed`, porta 8088)

| Rota | Contrato |
|---|---|
| `GET /v1/seed/hardware/ports` | Resposta `{"devices": [{"path", "label", "chipset", "suggested_board"?}]}`. Varredura em thread (`asyncio.to_thread`): `pyserial` se instalado (`hardware` extra), senão sysfs/glob em `/dev/ttyACM*`, `/dev/ttyUSB*`, `/dev/serial/by-id/*`. |
| `POST /v1/seed/export` | Body `{"target_board"?: "esp32_s3_devkitc1", "mission"?: <MissionState>}`. Usa última missão `SUCCESS` se `mission` omitido. `409` sem missão; `400` se não exportável. Resposta `export_path`, `archive_name`, `download_url`. Grava em `workspace/exports/`; domínios embedded (`esp_idf`, `lvgl_v9`) → PlatformIO (`platformio.ini`, `pinout_manifest.h`, `WIRING.md`); `python_fastapi` / `modbus_rtu` → bundle Python. |
| `GET /v1/seed/export/{archive_name}` | ZIP (`application/zip`). `400` se `..` ou `/` no nome; `404` se arquivo ausente em `workspace/exports/`. |
| `GET /v1/seed/stats` | Métricas do `mission_ledger` (PG ou fallback memória): `total_missions`, `local_missions`, `cloud_missions`, percentuais, `estimated_savings_usd`, `ledger_cloud_cost_usd`, gasto OpenRouter (`monthly_spend_usd`) vs `budget_cap_usd` (padrão $3.50), `budget_remaining_usd`, `validated_pairs` (`data/datasets/validated_pairs.jsonl`), `gpu_profile` (`GTX 1650 (local-first)`). |

## Módulos `src.yby_seed` (uv)

| Módulo | Comando |
|---|---|
| API | `make api` ou `uv run uvicorn src.yby_seed.main:app --port 8088` |
| Ingest RAG | `uv run python -m src.yby_seed.memory.ingest --dir ./docs --domain yby_arch` |
| Dataset synth | `uv run python -m src.yby_seed.forge.dataset_synth --count 5 --domain esp_idf` |
| Vast router | `uv run python -m src.yby_seed.forge.vast_router finetune-qlora --dry-run` |
| Deploy GGUF | `uv run python -m src.yby_seed.forge.deploy_model --preflight` |

## Testes

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest -v
```

O CI roda o mesmo em push/PR. Não precisa de Docker para o núcleo.

## O que não fazer

- Programar features do YBY em forks (`langgraph`, `llama.cpp`, …).
- Mesclar YBY / yby-core / FRANK_* para dentro deste repo.
- Colocar segredos no repositório.
- Tratar docs longos em `docs/` (arquitetura 7B, mobile, financiamento) como o caminho atual — ver [README do docs](README.md).
