# YBY SEED

PC Hub local-first para automações e IA.

## Status

Fase atual: **Fase 0 — Consolidação**. Foco exclusivo no PC (Ubuntu 26.04 LTS). Mobile e ESP32 ficam para fases futuras.

## O que é

YBY SEED é um hub central no PC que:

- Conversa localmente via Ollama.
- Executa automações seguras.
- Organiza e busca documentos.
- Usa nuvem apenas como fallback.

## MVP

O MVP funciona sem Docker:

```text
yby.py → RouterAgent → Ollama → resposta
```

## Início rápido

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull llama3.2:3b
python src/main.py
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
