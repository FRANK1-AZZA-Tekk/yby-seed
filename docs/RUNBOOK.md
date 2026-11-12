# RUNBOOK — pós-PR #59 (host local)

**CLI canônica:** `uv run python -m src.yby_seed.<módulo>` (não use `python -m yby_seed` sem `src.`).

Referência: **Ubuntu 26.04 LTS**, **GTX 1650 4 GB VRAM**, `num_ctx` 4096 no LiteLLM/Ollama.

## Sequência

1. **`make bootstrap`** — dependências de host (Docker, uv, drivers NVIDIA conforme `scripts/bootstrap_ubuntu.sh`).
2. **`make verify-host`** — valida GPU, Ollama e paths (`scripts/verify_host.py`).
3. **Dataset** — gerar/ampliar pares validados:
   ```bash
   uv run python -m src.yby_seed.forge.dataset_synth --help
   ```
   Saída canônica: `data/datasets/validated_pairs.jsonl`.
4. **Dry-run Vast (finetune-qlora)** — pré-voo do JSONL **antes** de qualquer busca na Vast:
   ```bash
   uv run python -m src.yby_seed.forge.vast_router finetune-qlora --dry-run --min-samples 20
   ```
   Status esperado com dataset ok: `dry_run_ok`. Sem dataset: `aborted_preflight_dataset`.
5. **Registro GGUF no Ollama** (após artefato local ou download do job):
   ```bash
   uv run python -m src.yby_seed.forge.deploy_model --register path/to/model.gguf
   ```
6. **`make install-service`** — unidade systemd user `yby-seed.service`.

## LiteLLM

Com `yby-seed-coder:latest` registrado, o proxy usa `yby-tuned` em `config/litellm_config.yaml` com fallback para `yby-local` se o modelo afinado não estiver disponível.

## API — hardware, export e economia

Subir API: `make api` (ou `uv run uvicorn src.yby_seed.main:app --host 127.0.0.1 --port 8088`).

| Rota | Uso operacional |
|---|---|
| `GET /v1/seed/hardware/ports` | Listar portas seriais no host Ubuntu antes de flash/upload. Preferência `pyserial` (`uv sync --extra hardware`); sem ele, leitura via `/dev/ttyACM*`, `/dev/ttyUSB*`, `/dev/serial/by-id/*` (sysfs). |
| `POST /v1/seed/export` | Exportar missão validada (`SUCCESS`) para `workspace/exports/`. JSON: `target_board` + `mission` opcional. Embedded → PlatformIO; Python/modbus → `pyproject.toml` + testes. |
| `GET /v1/seed/export/{archive_name}` | Baixar ZIP gerado pelo POST (nome retornado em `archive_name`). |
| `GET /v1/seed/stats` | Painel local-first: taxa local vs OpenRouter no ledger, economia estimada, teto mensal $3.50, amostras em `validated_pairs.jsonl`. |

Exemplo rápido após missão OK na UI:

```bash
curl -sS http://127.0.0.1:8088/v1/seed/stats | jq .
curl -sS http://127.0.0.1:8088/v1/seed/hardware/ports | jq .
curl -sS -X POST http://127.0.0.1:8088/v1/seed/export \
  -H 'Content-Type: application/json' \
  -d '{"target_board":"esp32_s3_devkitc1"}' | jq .
```
