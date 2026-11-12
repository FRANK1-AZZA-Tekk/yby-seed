# YBY SEED

[![CI](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml/badge.svg)](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/FRANK1-AZZA-Tekk/yby-seed/branch/main/graph/badge.svg)](https://codecov.io/gh/FRANK1-AZZA-Tekk/yby-seed)

PC Hub local-first para automações e IA. As decisões de 2026-11-11 estão em [DECISIONS.md](DECISIONS.md) e substituem as anteriores no mesmo assunto.

## Status

Fase atual: **Consolidação + exocórtex CLI**. O repositório tem **dois caminhos** oficiais (ver [docs/DEV.md](docs/DEV.md)):

| Caminho | Entrada | Modelo típico |
|---|---|---|
| **CLI v1** | `yby.py ask` / `yby skill` | Ollama `qwen2.5-coder:3b` (leve, sem Docker) |
| **Vibe Coding** | `make api` → `:8088` | LiteLLM `yby-tuned` → `yby-local` (**7B Q3_K_M**, GTX 1650 + Docker) |

Mobile e firmware ficam fora do v1.

## O que é

YBY SEED é o exocórtex pessoal nesse servidor:

- Conversa primeiro no Ollama, modelo `qwen2.5-coder:3b`.
- Sobe para a nuvem só em pedido pesado ou explícito. Padrão de nuvem: OpenRouter (modelo free); se falhar ou sem chave, Grok (xAI). Ambos OpenAI-compatíveis. Cache local + limite de contexto antes da chamada.
- A memória é um vault Obsidian em Markdown, com índice local. `python yby.py note` grava e `python yby.py recall` busca. O Syncthing sincroniza a pasta com o servidor de casa. O `ask` ainda não grava nota sozinho.
- Comandos de terminal seguem a allowlist em `config/safety-allowlist.txt` (leitura, git, scripts em `scripts/` e `examples/`). O resto pede sim ou não. `python yby.py run "..."` passa pela porta e, se permitido, executa com timeout. `python yby.py gate "..."` só decide; não executa.
- Voz opcional: `python yby.py listen` (ou `ask --voice`) grava até Enter, transcreve com faster-whisper e fala a resposta com Piper. Deps em `requirements-voice.txt`.
- No **CLI** (`ask`), o modelo local padrão é `qwen2.5-coder:3b`.
- No **stack Docker** (`src/yby_seed`), use `qwen2.5-coder:7b-instruct-q3_K_M` via LiteLLM (`config/litellm_config.yaml`).
- O gateway HTTP, se for usado, escuta em `127.0.0.1` e exige `GATEWAY_TOKEN`.
- Código gerado passa pela guarda AST em `src/security/ast_guard.py`.

## MVP

O MVP funciona sem Docker:

```text
yby.py ask → Ollama (qwen2.5-coder:3b) → resposta
                ↘ OpenRouter free → Grok, se o pedido for pesado ou explícito
yby.py skill → SkillManager → dry-run → confirmação → allowlist → ledger
make api     → yby_seed (7B Q3 via LiteLLM, sandbox Docker)
```

## Início rápido

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull qwen2.5-coder:3b
python yby.py ask "explica uma lista em Python"
```

`ask` responde em texto. Não executa shell e não grava memória. O modelo local padrão é `qwen2.5-coder:3b`. Pedidos longos, com várias perguntas, ou com frases como "pensa mais", vão para a nuvem (OpenRouter free → Grok). `--heavy` força esse caminho. As regras e os limites estão em `src/engine/routing.py` e nas variáveis `YBY_*` de `.env.example`.

Voz (opcional): `pip install -r requirements-voice.txt`, instale o binário Piper, defina `YBY_PIPER_MODEL`, e rode `python yby.py listen`. STT padrão: Whisper `base` em CPU. Sem essas deps, `ask` em texto segue normal.

Hub: `bash scripts/install-hub-service.sh --enable` ou `python yby.py hub`. Plataforma: [docs/PLATFORM.md](docs/PLATFORM.md).

Sem chave OpenRouter (`YBY_CLOUD_API_KEY` / `OPENROUTER_API_KEY`) nem Grok (`YBY_GROK_API_KEY` / `XAI_API_KEY`), a nuvem não é chamada: o comando avisa e, se o Ollama estiver no ar, responde no modelo local.

## Onde programar

O v1 mora neste repositório. Mapa e checklist de camadas: [docs/REPOS.md](docs/REPOS.md). Como rodar e testar: [docs/DEV.md](docs/DEV.md).

```text
feito:     engine | safety → actions | memory | voice | security/ast_guard
em curso:  Plataforma (D9) — hub systemd, Syncthing, OpenRouter→Grok, cache

yby.py            → comando
src/engine        → ask (+ cache / contexto nuvem)
src/platform      → hub keepalive
src/voice         → STT/TTS opcional (listen / ask --voice)
src/safety        → allowlist, decide (não executa)
src/actions       → executa após a porta
src/memory        → vault de notas
src/security      → guarda AST
tests/            → pytest
```

Agentes, RAG e gateway ficam em `src/`, fora desse caminho ([src/README.md](src/README.md)).

Mobile e firmware saíram do v1. Ver [docs/archive/FORA-DO-V1.md](docs/archive/FORA-DO-V1.md). Não programe features do YBY em forks; não coloque segredos no repo.

## Documentação

- [Índice dos docs](docs/README.md) (ativo vs histórico)
- [Onde programar](docs/REPOS.md)
- [Desenvolvimento](docs/DEV.md)
- [Plataforma](docs/PLATFORM.md)
- [Memória](docs/MEMORY.md)
- [Arquitetura](ARCHITECTURE.md)
- [Roadmap](ROADMAP.md)
- [Decisões](DECISIONS.md)
- [Hardware](HARDWARE_SPEC.md)
- [Model Card](MODEL_CARD.md)
- [Segurança](SECURITY.md)
