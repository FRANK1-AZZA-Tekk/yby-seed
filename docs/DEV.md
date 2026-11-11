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

Voz (`listen` / `ask --voice`) entra com o [PR #36](https://github.com/FRANK1-AZZA-Tekk/yby-seed/pull/36). Depois do merge: `pip install -r requirements-voice.txt`, binário Piper + `YBY_PIPER_MODEL`.

## Variáveis úteis (`.env`)

| Prefixo / chave | Uso |
|---|---|
| `YBY_OLLAMA_*`, `YBY_LOCAL_MODEL` | Ollama do `ask` |
| `YBY_CLOUD_*` ou `XAI_API_KEY` | nuvem (padrão Grok); sem chave = só local |
| `YBY_HEAVY_*` | limiares / frases que sobem para nuvem |
| `YBY_VAULT_PATH` | pasta do vault Obsidian |
| `GATEWAY_TOKEN`, `FASTAPI_HOST` | gateway HTTP (fora do caminho do `ask`) |
| `YBY_DATABASE_URL` | Postgres opcional (agentes legados) |

Roteamento do `ask`: `src/engine/routing.py` e `src/engine/config.py`.

## Onde editar

| Objetivo | Pastas |
|---|---|
| Resposta / provedores / roteamento | `src/engine/` |
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

## Testes

```bash
ruff check .
pytest -q
```

O CI roda o mesmo em push/PR. Não precisa de Docker para o núcleo.

## O que não fazer

- Programar features do YBY em forks (`langgraph`, `llama.cpp`, …).
- Mesclar YBY / yby-core / FRANK_* para dentro deste repo.
- Colocar segredos no repositório.
- Tratar docs longos em `docs/` (arquitetura 7B, mobile, financiamento) como o caminho atual — ver [README do docs](README.md).
