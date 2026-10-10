.PHONY: help setup install-dev test lint format run stop logs pull-models clean
PYTHON := python3
VENV := .venv
COMPOSE := docker compose

help:
	@echo "YBY SEED development commands: setup, install-dev, test, lint, format, run, stop, logs, pull-models, clean"

setup:
	@$(PYTHON) --version
	@$(PYTHON) -m venv $(VENV)
	@$(VENV)/bin/python -m pip install --upgrade pip
	@$(VENV)/bin/pip install -r requirements.txt -r requirements-dev.txt
	@test -f .env || (cp .env.example .env && echo "Criado .env; edite credenciais antes do make run")
	@echo "Dependências instaladas. Não baixa modelos nem inicia Docker automaticamente."

install-dev:
	@$(VENV)/bin/pip install -r requirements-dev.txt

test:
	@$(VENV)/bin/pytest tests/ -q

lint:
	@$(VENV)/bin/flake8 src/ tests/ --count --select=E9,F63,F7,F82 --show-source --statistics

format:
	@$(VENV)/bin/black src/ tests/

run:
	@test -f .env || (echo "Crie .env a partir de .env.example" && exit 1)
	@$(COMPOSE) up -d --wait

pull-models:
	@$(COMPOSE) exec ollama ollama pull qwen2.5-coder:3b-instruct-q4_K_M

stop:
	@$(COMPOSE) down

logs:
	@$(COMPOSE) logs -f

clean:
	rm -rf .pytest_cache .mypy_cache dist build *.egg-info
	find . -type f -name '*.pyc' -delete
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
