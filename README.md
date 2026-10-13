# YBY SEED

PC Hub local-first para automações e IA.

## Escopo atual

Foco exclusivo no PC (Ubuntu 26.04 LTS). Mobile e ESP32 ficam para fases futuras.

## Stack

- Ollama (local)
- OpenRouter (fallback)
- LiteLLM
- FastAPI
- Qdrant
- PostgreSQL
- Redis
- Docker Compose

## Início rápido

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install litellm pydantic requests pytest
ollama pull llama3.2:3b
```

## Documentação

- [Plano PC-first](docs/PLANO-PC-FIRST.md)
- [Otimizações e gargalos](docs/OTIMIZACOES.md)
