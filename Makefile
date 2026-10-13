# YBY SEED — Makefile local-first
# Uso: make [comando]

.PHONY: help setup install-dev doctor test lint format run stop logs docs clean nomad-help nomad-doctor nomad-install nomad-up nomad-down nomad-restart nomad-logs nomad-status nomad-open

PYTHON := python3
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip

NOMAD_DIR := /opt/project-nomad
NOMAD_URL := http://localhost:8080
NOMAD_REPO := https://github.com/Crosstalk-Solutions/project-nomad.git
NOMAD_SOURCE := $(HOME)/yby/external/project-nomad

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
	@echo "🧭 NOMAD:"
	@echo "  make nomad-help     - Mostra comandos do Project NOMAD"
	@echo "  make nomad-doctor   - Verifica Docker, instalação e serviço"
	@echo "  make nomad-install  - Clona e prepara o instalador do NOMAD"
	@echo "  make nomad-up       - Inicia o NOMAD"
	@echo "  make nomad-down     - Para o NOMAD"
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

# ===== Project NOMAD =====

nomad-help:
	@echo "🧭 NOMAD — Comandos disponíveis"
	@echo ""
	@echo "  make nomad-doctor   - Verifica Docker, instalação e serviço do NOMAD"
	@echo "  make nomad-install  - Clona e prepara o instalador do NOMAD"
	@echo "  make nomad-up       - Inicia o NOMAD"
	@echo "  make nomad-down     - Para o NOMAD"
	@echo "  make nomad-restart  - Reinicia o NOMAD"
	@echo "  make nomad-logs     - Acompanha os logs do NOMAD"
	@echo "  make nomad-status   - Verifica se $(NOMAD_URL) responde"
	@echo "  make nomad-open     - Abre o NOMAD no navegador padrão"

nomad-doctor:
	@echo "🧭 Verificando NOMAD..."
	@command -v docker >/dev/null 2>&1 || { \
		echo "❌ Docker não encontrado."; \
		exit 1; \
	}
	@if [ ! -d "$(NOMAD_DIR)" ]; then \
		echo "❌ NOMAD não está instalado em $(NOMAD_DIR)."; \
		echo "   Execute: make nomad-install"; \
		exit 1; \
	fi
	@echo "✅ NOMAD instalado em $(NOMAD_DIR)."

nomad-install:
	@echo "⬇️  Preparando Project NOMAD..."
	@mkdir -p $(HOME)/yby/external
	@if [ ! -d "$(NOMAD_SOURCE)" ]; then \
		git clone $(NOMAD_REPO) $(NOMAD_SOURCE); \
	fi
	@echo "⚠️  Revise o instalador antes de executar:"
	@echo "   less $(NOMAD_SOURCE)/install/install_nomad.sh"
	@echo ""
	@echo "Depois execute manualmente:"
	@echo "   sudo bash $(NOMAD_SOURCE)/install/install_nomad.sh"

nomad-up:
	@$(MAKE) nomad-doctor
	@echo "🚀 Iniciando NOMAD..."
	@sudo bash $(NOMAD_DIR)/start_nomad.sh
	@$(MAKE) nomad-status

nomad-down:
	@$(MAKE) nomad-doctor
	@echo "🛑 Parando NOMAD..."
	@sudo bash $(NOMAD_DIR)/stop_nomad.sh

nomad-restart:
	@$(MAKE) nomad-down
	@$(MAKE) nomad-up

nomad-logs:
	@$(MAKE) nomad-doctor
	@sudo bash $(NOMAD_DIR)/logs.sh

nomad-status:
	@echo "🔍 Verificando $(NOMAD_URL)..."
	@curl -fsS --max-time 5 $(NOMAD_URL) >/dev/null && \
		echo "✅ NOMAD acessível em $(NOMAD_URL)" || \
		{ echo "❌ NOMAD não responde em $(NOMAD_URL)"; exit 1; }

nomad-open:
	@xdg-open $(NOMAD_URL)
