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
