# YBY SEED - Makefile para desenvolvimento local
# Uso: make [comando]

.PHONY: help setup test run stop logs clean docs lint format install-dev

PYTHON := python3
VENV := .venv
DOCKER_COMPOSE := docker compose

help:
	@echo "YBY SEED - comandos disponíveis"
	@echo "  make setup       - Cria .venv e instala requirements.txt (sem baixar modelos)"
	@echo "  make install-dev - Instala requirements-dev.txt na .venv"
	@echo "  make test        - Executa os testes com pytest"
	@echo "  make lint        - Executa flake8 em src/ e tests/"
	@echo "  make format      - Formata src/ e tests/ com black"
	@echo "  make run         - Inicia apenas Qdrant pelo Docker Compose"
	@echo "  make stop        - Para o serviço Docker Compose"
	@echo "  make logs        - Mostra logs do Docker Compose"
	@echo "  make docs        - Informa o estado da documentação"
	@echo "  make clean       - Remove caches e o ambiente virtual"

setup:
	@echo "Criando ambiente virtual e instalando dependências Python..."
	@$(PYTHON) -m venv $(VENV)
	@$(VENV)/bin/python -m pip install --upgrade pip
	@$(VENV)/bin/python -m pip install -r requirements.txt
	@echo "Dependências Python instaladas. Modelos e serviços opcionais não são configurados por este comando."

install-dev:
	@test -x $(VENV)/bin/python || (echo "Execute make setup antes de make install-dev." >&2; exit 1)
	@$(VENV)/bin/python -m pip install -r requirements-dev.txt

test:
	@test -x $(VENV)/bin/pytest || (echo "pytest não encontrado; execute make setup e make install-dev." >&2; exit 1)
	@$(VENV)/bin/pytest tests/ -v --tb=short

lint:
	@test -x $(VENV)/bin/flake8 || (echo "flake8 não encontrado; execute make install-dev." >&2; exit 1)
	@$(VENV)/bin/flake8 src/ tests/ --count --select=E9,F63,F7,F82 --show-source --statistics

format:
	@test -x $(VENV)/bin/black || (echo "black não encontrado; execute make install-dev." >&2; exit 1)
	@$(VENV)/bin/black src/ tests/

run:
	@echo "Iniciando somente Qdrant (127.0.0.1:6333) pelo Docker Compose..."
	@$(DOCKER_COMPOSE) up -d qdrant
	@echo "Qdrant iniciado; Node-RED, Ollama e o app YBY não são iniciados por make run."

stop:
	@$(DOCKER_COMPOSE) down

logs:
	@$(DOCKER_COMPOSE) logs -f

docs:
	@echo "A documentação está em docs/; não há servidor MkDocs configurado neste alvo."

clean:
	@rm -rf __pycache__/ .pytest_cache/ .mypy_cache/ .venv/ dist/ build/ *.egg-info
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@echo "Caches locais removidos."
