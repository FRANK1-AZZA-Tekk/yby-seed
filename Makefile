# YBY SEED - Makefile alinhado ao estado real do repositório
# Uso: make [comando]

.PHONY: help setup install-dev doctor test lint format run brief status stop clean

PYTHON := python3
VENV := .venv
BIN := $(VENV)/bin

help:
	@echo "YBY SEED - Comandos Disponíveis"
	@echo ""
	@echo "  make setup        - Cria .venv e instala dependências Python"
	@echo "  make install-dev  - Instala dependências de desenvolvimento"
	@echo "  make doctor       - Diagnostica o ambiente local"
	@echo "  make test         - Roda pytest (unitários)"
	@echo "  make lint         - Ruff + mypy"
	@echo "  make format       - Formata com ruff"
	@echo "  make status       - Mostra o estado declarado do projeto"
	@echo "  make brief        - Briefing revisável (exporta .yby/briefings/)"
	@echo "  make run          - REPL do framework (Camada A)"
	@echo "  make stop         - Para containers do docker compose (se houver)"
	@echo "  make clean        - Remove caches locais"
	@echo ""
	@echo "Nota: docker-compose.yml sobe apenas Qdrant (pós-MVP)."

setup:
	@echo "Configurando ambiente Python local..."
	@$(PYTHON) -m venv $(VENV)
	@$(BIN)/pip install --upgrade pip
	@$(BIN)/pip install -r requirements.txt -r requirements-dev.txt
	@echo "Setup OK. Próximo: make doctor && make test"

install-dev:
	@$(BIN)/pip install -r requirements-dev.txt

doctor:
	@$(BIN)/python src/main.py doctor

test:
	@$(BIN)/python src/main.py test

lint:
	@$(BIN)/ruff check src tests
	@$(BIN)/mypy src tests

format:
	@$(BIN)/ruff check --fix src tests
	@$(BIN)/ruff format src tests

status:
	@$(BIN)/python src/main.py status

brief:
	@$(BIN)/python src/main.py brief

run:
	@$(BIN)/python src/main.py run

stop:
	@docker compose down || true

clean:
	@rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/ htmlcov/ coverage.xml
	@find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	@echo "Limpeza OK"
