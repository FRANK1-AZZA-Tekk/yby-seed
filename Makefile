# YBY SEED — atalhos alinhados ao CI (doctor + ruff + pytest)
# Guia: docs/DEV.md

.PHONY: help setup install-dev doctor lint test check clean qdrant-up qdrant-down twatch-backup twatch-build twatch-flash twatch-monitor hil-qa

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
	@echo "  make doctor       checagem honesta do ambiente (igual CI)"
	@echo "  make lint         ruff check src tests (igual CI)"
	@echo "  make test         pytest tests -q (igual CI)"
	@echo "  make check        doctor + lint + test"
	@echo "  make qdrant-up    sobe Qdrant opcional (RAG legado)"
	@echo "  make qdrant-down  para Qdrant"
	@echo "  make twatch-backup  backup 16 MB da flash do T-Watch S3 Plus"
	@echo "  make twatch-build   compila firmware PlatformIO (sem LoRa)"
	@echo "  make twatch-flash   grava firmware via USB (exige backup prévio)"
	@echo "  make twatch-monitor abre monitor serial USB do T-Watch"
	@echo "  make hil-qa         executa QA Hardware-in-the-Loop dos 4 nós"
	@echo "  make clean        cache pytest/ruff e __pycache__"
	@echo ""
	@echo "Núcleo: ollama pull qwen2.5-coder:3b && python yby.py ask \"...\""

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

doctor:
	PYTHONPATH=. $(PY) scripts/doctor.py

lint:
	PYTHONPATH=. $(PY) -m ruff check src tests

test:
	PYTHONPATH=. $(PY) -m pytest tests -q

check: doctor lint test

qdrant-up:
	docker compose up -d qdrant

qdrant-down:
	docker compose stop qdrant

twatch-backup:
	PYTHONPATH=. $(PY) -m scripts.twatch.backup

twatch-build:
	PYTHONPATH=. $(PY) -m scripts.twatch.build

twatch-flash:
	PYTHONPATH=. $(PY) -m scripts.twatch.flash

twatch-monitor:
	PYTHONPATH=. $(PY) -m scripts.twatch.monitor

hil-qa:
	PYTHONPATH=. $(PY) -m scripts.hil_qa_4nodes

clean:
	rm -rf .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
