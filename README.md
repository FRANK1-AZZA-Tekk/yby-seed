# YBY SEED

[![CI](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml/badge.svg)](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/FRANK1-AZZA-Tekk/yby-seed/branch/main/graph/badge.svg)](https://codecov.io/gh/FRANK1-AZZA-Tekk/yby-seed)

PC Hub local-first para automações e IA.

## Status

Fase atual: **Fase 1 — Briefing revisável (MVP)**. Foco exclusivo no PC. Mobile e ESP32 ficam para fases futuras.

**Implementado hoje:** `doctor`, `setup`, `test`, `status`, `brief`.  
**Ainda não implementado:** hub completo (`run`), Node-RED, MQTT.  
**Docker Compose:** apenas Qdrant (pós-MVP / Fase 5).

## O que é

YBY SEED é um hub central no PC que pretende:

- Conversar localmente via Ollama.
- Executar automações seguras (dry-run primeiro).
- Organizar e buscar documentos.
- Usar nuvem apenas como fallback.

## MVP (alvo)

```text
pedido PT → perguntas mínimas → briefing → revisão → export MD+JSON
```

Sem execução automática de código. Hub completo / skills ficam para fases seguintes.

## Início rápido

```bash
make setup
make doctor
make test
python src/main.py status
```

## Briefing revisável

Entrada primária:

```bash
# Interativo (pede pedido + perguntas; Ollama local)
python src/main.py brief

# Não-interativo (útil em scripts)
python src/main.py brief \
  --request "Quero backup diário dos documentos" \
  --answer "~/Documentos" \
  --answer "/mnt/backup" \
  --approve
```

Exporta Markdown + JSON em `.yby/briefings/` (já no `.gitignore`).
Nenhuma execução automática de código.

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
