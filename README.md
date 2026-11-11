# YBY SEED

[![CI](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml/badge.svg)](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/FRANK1-AZZA-Tekk/yby-seed/branch/main/graph/badge.svg)](https://codecov.io/gh/FRANK1-AZZA-Tekk/yby-seed)

PC Hub local-first para automações e IA. As decisões de 2026-11-11 estão em [DECISIONS.md](DECISIONS.md) e substituem as anteriores no mesmo assunto.

## Status

Fase atual: **Fase 0 — Consolidação**. A plataforma decidida é o servidor de casa sempre ligado (o PC Hub, Ubuntu). Mobile e firmware ficaram fora do v1.

## O que é

YBY SEED é o exocórtex pessoal nesse servidor:

- Conversa primeiro no Ollama, modelo `qwen2.5-coder:3b`.
- Sobe para a nuvem só em pedido pesado ou explícito. O padrão é Grok (xAI), num endpoint compatível com a API da OpenAI. OpenRouter fica como configuração alternativa.
- A memória é um vault Obsidian em Markdown, com índice local. `python yby.py note` grava e `python yby.py recall` busca. O Syncthing sincroniza a pasta com o servidor de casa. O `ask` ainda não grava nota sozinho.
- Comandos de terminal seguem a allowlist em `config/safety-allowlist.txt` (leitura, git, scripts em `scripts/` e `examples/`). O resto pede sim ou não. `python yby.py run "..."` passa pela porta e, se permitido, executa com timeout. `python yby.py gate "..."` só decide; não executa.
- O único modelo local é `qwen2.5-coder:3b`.
- O gateway HTTP, se for usado, escuta em `127.0.0.1` e exige `GATEWAY_TOKEN`.
- Código gerado passa pela guarda AST em `src/security/ast_guard.py`.

## MVP

O MVP funciona sem Docker:

```text
yby.py ask → Ollama (qwen2.5-coder:3b) → resposta
                ↘ Grok, se o pedido for pesado ou explícito
```

## Início rápido

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull qwen2.5-coder:3b
python yby.py ask "explica uma lista em Python"
```

`ask` responde em texto. Não executa shell, não grava memória e não usa voz. O modelo local padrão é `qwen2.5-coder:3b`. Pedidos longos, com várias perguntas, ou com frases como "pensa mais", vão para a nuvem (Grok, endpoint compatível com a API da OpenAI). `--heavy` força esse caminho. As regras e os limites estão em `src/engine/routing.py` e nas variáveis `YBY_*` de `.env.example`.

Sem `YBY_CLOUD_API_KEY` (ou `XAI_API_KEY`), a nuvem não é chamada: o comando avisa e, se o Ollama estiver no ar, responde no modelo local.

## Onde programar

O v1 mora neste repositório. Mapa e checklist de camadas: [docs/REPOS.md](docs/REPOS.md). Como rodar e testar: [docs/DEV.md](docs/DEV.md).

```text
feito:   yby.py → engine | safety → actions | memory | security/ast_guard
aberto:  voice (PR #36)
próximo: Plataforma (servidor de casa / D9) — sem merge de YBY/yby-core/FRANK
```

Agentes, RAG e gateway ficam em `src/`, fora desse caminho ([src/README.md](src/README.md)).

Mobile e firmware saíram do v1. Ver [docs/archive/FORA-DO-V1.md](docs/archive/FORA-DO-V1.md). Não programe features do YBY em forks; não coloque segredos no repo.

## Documentação

- [Índice dos docs](docs/README.md) (ativo vs histórico)
- [Onde programar](docs/REPOS.md)
- [Desenvolvimento](docs/DEV.md)
- [Memória](docs/MEMORY.md)
- [Arquitetura](ARCHITECTURE.md)
- [Roadmap](ROADMAP.md)
- [Decisões](DECISIONS.md)
- [Hardware](HARDWARE_SPEC.md)
- [Model Card](MODEL_CARD.md)
- [Segurança](SECURITY.md)
