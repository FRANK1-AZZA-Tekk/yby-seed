# YBY SEED — Makefile local-first
# Uso: make [comando]

.PHONY: help setup install-dev doctor test lint format run stop logs docs clean

PYTHON := python3
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip

help:
	@echo "🌱 YBY SEED — Comandos disponíveis"
	@echo ""
	@echo "📦 Ambiente:"
	@echo "  make setup        - Cria o venv, instala dependências e valida o ambiente"
	@echo "  make install-dev  - Instala dependências de desenvolvimento"
	@echo "  make doctor       - Diagnostica Python, dependências, estrutura e Ollama"
	@echo ""
	@echo "🧪 Qualidade:"
	@echo "  make test         - Executa a suíte de testes"
	@echo "  make lint         - Verifica erros críticos com flake8"
	@echo "  make format       - Formata o código com black"
	@echo ""
	@echo "🚀 Execução:"
	@echo "  make run          - Inicia o núcleo local do YBY SEED"
	@echo ""
	@echo "📚 Documentação:"
	@echo "  make docs         - Inicia a documentação local, se configurada"
	@echo ""
	@echo "🧹 Limpeza:"
	@echo "  make clean        - Remove caches e artefatos temporários"

setup:
	@echo "🌱 Preparando ambiente local..."
	$(PYTHON) -m venv $(VENV)
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -r requirements.txt
	$(VENV_PYTHON) src/main.py setup

install-dev:
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -r requirements-dev.txt

doctor:
	$(VENV_PYTHON) src/main.py doctor

test:
	$(VENV_PYTHON) src/main.py test

lint:
	$(VENV_PYTHON) -m flake8 src/ tests/ --count --select=E9,F63,F7,F82 --show-source --statistics

format:
	$(VENV_PYTHON) -m black src/ tests/

run:
	$(VENV_PYTHON) src/main.py run

stop:
	@echo "ℹ️  Nenhum serviço Docker é iniciado pelo MVP local-first."

logs:
	@echo "📋 Logs disponíveis em: logs/"

docs:
	@if [ -f docs/mkdocs.yml ] || [ -f mkdocs.yml ]; then \
		$(VENV_PYTHON) -m mkdocs serve; \
	else \
		echo "❌ Documentação MkDocs ainda não está configurada."; \
		exit 1; \
	fi

clean:
	@echo "🧹 Limpando artefatos temporários..."
	@rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache dist build *.egg-info
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	@echo "✅ Limpeza concluída."
