# YBY SEED - Makefile para Programadores Iniciantes
# Uso: make [comando]
# Exemplo: make setup, make test, make run

.PHONY: help setup test run stop clean docs lint format install-dev

# Variáveis
PYTHON := python3
PIP := pip3
VENV := .venv
DOCKER := docker
DOCKER_COMPOSE := docker compose

# Target padrão (ajuda)
help:
	@echo "🌱 YBY SEED - Comandos Disponíveis"
	@echo ""
	@echo "📦 Instalação:"
	@echo "  make setup          - Instala dependências e configura ambiente"
	@echo "  make install-dev    - Instala dependências de desenvolvimento"
	@echo ""
	@echo "🧪 Testes:"
	@echo "  make test           - Roda todos os testes"
	@echo "  make lint           - Verifica qualidade do código (flake8)"
	@echo "  make format         - Formata código automaticamente (black)"
	@echo ""
	@echo "🚀 Execução:"
	@echo "  make run            - Inicia todos os serviços (Docker)"
	@echo "  make stop           - Para todos os serviços"
	@echo "  make logs           - Mostra logs em tempo real"
	@echo ""
	@echo "📚 Documentação:"
	@echo "  make docs           - Gera documentação local (MkDocs)"
	@echo ""
	@echo "🧹 Limpeza:"
	@echo "  make clean          - Remove arquivos temporários e cache"
	@echo ""
	@echo "💡 Dicas:"
	@echo "  - Use 'make' seguido do comando desejado"
	@echo "  - Exemplo: 'make setup' instala tudo que precisa"
	@echo "  - Use 'make help' para ver esta ajuda novamente"

# Instala dependências e configura ambiente
setup:
	@echo "🌱 Configurando YBY SEED..."
	@echo ""
	@echo "[1/5] Verificando Python..."
	@$(PYTHON) --version
	@echo ""
	@echo "[2/5] Criando ambiente virtual..."
	@$(PYTHON) -m venv $(VENV)
	@echo ""
	@echo "[3/5] Instalando dependências..."
	@$(VENV)/bin/pip install --upgrade pip
	@$(VENV)/bin/pip install -r requirements.txt
	@echo ""
	@echo "[4/5] Verificando Docker..."
	@$(DOCKER) --version
	@$(DOCKER_COMPOSE) --version
	@echo ""
	@echo "[5/5] Baixando modelos Ollama..."
	@$(DOCKER_COMPOSE) exec -T ollama ollama pull llama3.2:3b-instruct-q4_K_M || true
	@$(DOCKER_COMPOSE) exec -T ollama ollama pull qwen2.5-coder:3b-instruct-q4_K_M || true
	@echo ""
	@echo "✅ Setup concluído!"
	@echo ""
	@echo "🎉 Próximo passo: execute 'make run' para iniciar o sistema"
	@echo "📚 Leia docs/tutorials/01-first-steps.md para começar"

# Instala dependências de desenvolvimento
install-dev:
	@echo "🛠️  Instalando dependências de desenvolvimento..."
	@$(VENV)/bin/pip install -r requirements-dev.txt
	@echo "✅ Dependências de desenvolvimento instaladas!"

# Roda testes

test:
	@echo "🧪 Rodando testes..."
	@$(VENV)/bin/pytest tests/ -v --tb=short
	@echo ""
	@echo "✅ Testes concluídos!"

# Verifica qualidade do código
lint:
	@echo "🔍 Verificando qualidade do código..."
	@$(VENV)/bin/flake8 src/ tests/ --count --select=E9,F63,F7,F82 --show-source --statistics
	@echo ""
	@echo "✅ Verificação concluída!"

# Formata código automaticamente
format:
	@echo "🎨 Formatando código..."
	@$(VENV)/bin/black src/ tests/
	@echo "✅ Código formatado!"

# Inicia todos os serviços
run:
	@echo "🚀 Iniciando YBY SEED..."
	@$(DOCKER_COMPOSE) up -d
	@echo ""
	@echo "✅ Serviços iniciados!"
	@echo ""
	@echo "📌 Acesse:"
	@echo "   - Node-RED: http://localhost:1880"
	@echo "   - Ollama: http://localhost:11434"
	@echo ""
	@echo "📚 Veja logs: make logs"
	@echo "🛑 Pare: make stop"

# Para todos os serviços
stop:
	@echo "🛑 Parando YBY SEED..."
	@$(DOCKER_COMPOSE) down
	@echo "✅ Serviços parados!"

# Mostra logs em tempo real
logs:
	@$(DOCKER_COMPOSE) logs -f

# Gera documentação local
docs:
	@echo "📚 Gerando documentação..."
	@cd docs && mkdocs serve
	@echo ""
	@echo "✅ Documentação disponível em http://localhost:8000"

# Limpa arquivos temporários
clean:
	@echo "🧹 Limpando arquivos temporários..."
	@rm -rf __pycache__/
	@rm -rf .pytest_cache/
	@rm -rf .mypy_cache/
	@rm -rf .venv/
	@rm -rf dist/
	@rm -rf build/
	@rm -rf *.egg-info
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@echo "✅ Limpeza concluída!"
