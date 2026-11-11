# YBY SEED

[![CI](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml/badge.svg)](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/FRANK1-AZZA-Tekk/yby-seed/branch/main/graph/badge.svg)](https://codecov.io/gh/FRANK1-AZZA-Tekk/yby-seed)

PC Hub local-first para automações e IA.

## Status

Fase atual: **Fase 0 — Consolidação / recuperação**. Foco exclusivo no PC. Mobile e ESP32 ficam para fases futuras.

**Implementado hoje:** `doctor`, `setup`, `test`, `status` (CLI honesta).  
**Ainda não implementado:** hub completo (`run`), Node-RED, MQTT, briefing revisável (Fase 1).  
**Docker Compose:** apenas Qdrant (pós-MVP / Fase 5).

## O que é

YBY SEED é um hub central no PC que pretende:

- Conversar localmente via Ollama.
- Executar automações seguras (dry-run primeiro).
- Organizar e buscar documentos.
- Usar nuvem apenas como fallback.

## MVP (alvo)

```text
CLI → RouterAgent → Ollama → resposta
```

Esse fluxo ponta a ponta ainda está em construção. Use `doctor`/`test` para validar o estado real.

## Início rápido

```bash
make setup
make doctor
make test
python src/main.py status
```

## Estrutura

```text
src/       → núcleo YBY
skills/    → automações
tests/     → testes
scripts/   → utilitários
docs/      → planos e decisões
examples/  → exemplos (pós-MVP)
grafana/   → observabilidade (pós-MVP)
firmware/  → futuro (ESP32)
```

## Documentação

- [Arquitetura](ARCHITECTURE.md)
- [Roadmap](ROADMAP.md)
- [Decisões](DECISIONS.md)
- [Hardware](HARDWARE_SPEC.md)
- [Model Card](MODEL_CARD.md)
- [Segurança](SECURITY.md)
- [Plano PC-first](docs/PLANO-PC-FIRST.md)
- [Otimizações](docs/OTIMIZACOES.md)
