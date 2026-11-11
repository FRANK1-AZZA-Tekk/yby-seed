# YBY SEED

[![CI](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml/badge.svg)](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/FRANK1-AZZA-Tekk/yby-seed/branch/main/graph/badge.svg)](https://codecov.io/gh/FRANK1-AZZA-Tekk/yby-seed)

PC Hub local-first para automações e IA. **Repositório canônico** do ecossistema YBY.

## Status

Fase atual: **Fase 0 — Consolidação**. Foco exclusivo no PC (Ubuntu 26.04 LTS). Mobile e ESP32 ficam para fases futuras.

O melhor de `YBY`, `yby-core` e `yby-seed-local` foi absorvido aqui. Ver [mapa de repositórios](docs/REPO_MAP.md).

## O que é

YBY SEED é um hub central no PC que:

- Conversa localmente via Ollama.
- Executa automações seguras.
- Organiza e busca documentos.
- Usa nuvem apenas como fallback.
- Aplica privacidade P0–P3 e degradação segura (núcleo YBY ZERO).

## MVP

O MVP funciona sem Docker:

```text
src/main.py → RouterAgent → Ollama → resposta
```

Modelo-padrão validado no hardware alvo: `qwen2.5-coder:3b` ([benchmarks](docs/benchmarks/README.md)).

## Início rápido

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
ollama pull qwen2.5-coder:3b
python src/main.py
pytest tests/test_yby_zero tests/test_orchestrator.py -q
```

## Estrutura

```text
src/yby_zero/      → eventos, privacidade, degradação, roteamento de provider
src/orchestrator/  → classificação de tarefa + escolha de modelo
src/agents/        → Router / Planning / Validation / Execution
src/tools/         → ferramentas com jail em ~/yby
integrations/      → espelho opcional do yby-core (LangGraph)
skills/            → automações
tests/             → testes
scripts/           → utilitários e benchmarks
docs/              → planos, mapa de repos e decisões
firmware/          → futuro (ESP32)
```

## Documentação

- [Mapa de repositórios](docs/REPO_MAP.md)
- [YBY Core](docs/YBY_CORE.md)
- [Arquitetura](ARCHITECTURE.md)
- [Roadmap](ROADMAP.md)
- [Decisões](DECISIONS.md)
- [Hardware](HARDWARE_SPEC.md)
- [Capacidade de hardware](docs/CAPACIDADE-HARDWARE.md)
- [Benchmarks](docs/benchmarks/README.md)
- [Model Card](MODEL_CARD.md)
- [Segurança](SECURITY.md)
- [Plano PC-first](docs/PLANO-PC-FIRST.md)
