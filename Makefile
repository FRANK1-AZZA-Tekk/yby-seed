# YBY SEED — atalhos alinhados ao CI (ruff + pytest em src/tests)
# Guia completo: docs/DEV.md

.PHONY: help setup install-dev test lint check clean qdrant-up qdrant-down

PYTHON := python3
VENV := .venv
VENV_BIN := $(VENV)/bin
ifeq ($(wildcard $(VENV_BIN)/python),)
  PY := $(PYTHON)
else
  PY := $(VENV_BIN)/python
endif

help:
	@echo "YBY SEED — comandos"
	@echo ""
	@echo "  make setup        venv + requirements (+ dev)"
	@echo "  make install-dev  só requirements-dev.txt"
	@echo "  make lint         ruff check src tests (igual CI)"
	@echo "  make test         pytest tests -q"
	@echo "  make check        lint + test"
	@echo "  make qdrant-up    sobe Qdrant opcional (RAG legado)"
	@echo "  make qdrant-down  para Qdrant"
	@echo "  make clean        cache pytest/ruff e __pycache__"
	@echo ""
	@echo "Núcleo v1: ollama pull qwen2.5-coder:3b && python yby.py ask \"...\""

setup: $(VENV_BIN)/pip
	$(VENV_BIN)/pip install --upgrade pip
	$(VENV_BIN)/pip install -r requirements.txt -r requirements-dev.txt
	@echo ""
	@echo "Setup OK. Próximo: ollama pull qwen2.5-coder:3b"
	@echo "Leia: docs/DEV.md"

$(VENV_BIN)/pip:
	$(PYTHON) -m venv $(VENV)

install-dev: $(VENV_BIN)/pip
	$(VENV_BIN)/pip install -r requirements-dev.txt

lint:
	PYTHONPATH=. $(PY) -m ruff check src tests

test:
	PYTHONPATH=. $(PY) -m pytest tests -q

check: lint test

qdrant-up:
	docker compose up -d qdrant

qdrant-down:
	docker compose stop qdrant

clean:
	rm -rf .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
