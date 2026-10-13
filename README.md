# YBY SEED

[![CI](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml/badge.svg)](https://github.com/FRANK1-AZZA-Tekk/yby-seed/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/FRANK1-AZZA-Tekk/yby-seed/branch/main/graph/badge.svg)](https://codecov.io/gh/FRANK1-AZZA-Tekk/yby-seed)

PC Hub local-first para automações e IA.

## Status

Fase atual: **Fase 0 — Consolidação**. O foco é o PC (Ubuntu 26.04 LTS); mobile e ESP32 ficam para fases futuras.

O projeto está em consolidação: a CLI existe, mas ainda não inicia um sistema completo de IA ou automação. Não há integração funcional com Ollama, Node-RED ou MQTT nesta fase.

## O que já existe

- Estrutura inicial do projeto e testes automatizados.
- CLI de desenvolvimento em `src/main.py`.
- Serviço opcional Qdrant via Docker Compose.
- Ferramentas de teste, lint e formatação.

## O que ainda não funciona

- `python src/main.py run` não inicia Ollama, Node-RED, MQTT ou o sistema YBY completo.
- `python src/main.py test` não substitui a suíte de testes; use `make test`.
- `python src/main.py setup` não substitui `make setup`.
- Não há download automático de modelos nem integração funcional com Ollama.

## Início rápido

```bash
make setup
make test
```

Para iniciar apenas o Qdrant local:

```bash
make run
```

O Qdrant fica disponível em `http://127.0.0.1:6333`. O comando não inicia Node-RED, Ollama ou o app YBY.

## Comandos

| Comando | O que faz hoje |
|---|---|
| `make setup` | Cria `.venv` e instala dependências Python. |
| `make install-dev` | Instala dependências de desenvolvimento. |
| `make test` | Executa os testes com pytest. |
| `make lint` | Executa verificações básicas com flake8. |
| `make format` | Formata o código com black. |
| `make run` | Inicia somente o Qdrant via Docker Compose. |
| `make stop` | Para os serviços do Docker Compose. |
| `make logs` | Mostra os logs do Docker Compose. |

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
