# ============================================================================
# Makefile - Orchestrator Service
# ============================================================================
# Comandos padronizados para desenvolvimento, testes e deploy
# 
# Uso: make <target>
# Lista de comandos: make help
# ============================================================================

.PHONY: help
.DEFAULT_GOAL := help

# ============================================================================
# VARIÁVEIS
# ============================================================================

DOCKER_COMPOSE := docker compose
SERVICE_NAME := orchestrator
PYTHON := python3
VENV := .venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PYTEST := $(VENV_BIN)/pytest
API_BASE_URL := http://localhost:8000
PORT ?= 8000

# ============================================================================
# HELP
# ============================================================================

help: ## Mostrar esta mensagem de ajuda
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║          Orchestrator Service - Comandos Disponíveis           ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "📚 Categorias:"
	@echo "  • Desenvolvimento: install, venv, dev, shell"
	@echo "  • Testes: test, test-unit, test-integration"
	@echo "  • Docker: build, up, down, restart, logs, ps"
	@echo "  • API: health, status, jobs"
	@echo "  • Manutenção: clean, clean-all, validate"
	@echo ""

# ============================================================================
# DESENVOLVIMENTO
# ============================================================================

venv: ## Criar virtual environment (.venv)
	@echo "🐍 Criando virtual environment..."
	@if [ ! -d "$(VENV)" ]; then \
		$(PYTHON) -m venv $(VENV); \
		echo "✅ Virtual environment criado: $(VENV)"; \
		echo "💡 Ativar: source $(VENV)/bin/activate"; \
	else \
		echo "✅ Virtual environment já existe: $(VENV)"; \
	fi

install: venv ## Instalar dependências Python no venv
	@echo "📦 Instalando dependências no venv..."
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements.txt
	@echo "✅ Dependências instaladas!"

dev: ## Rodar serviço em modo desenvolvimento (local, sem Docker)
	@echo "🚀 Iniciando $(SERVICE_NAME) em modo dev..."
	@echo "   Port: $(PORT)"
	PORT=$(PORT) $(VENV_PYTHON) run.py

shell: ## Abrir shell Python com ambiente configurado
	@echo "🐍 Abrindo Python shell..."
	$(VENV_PYTHON)

# ============================================================================
# TESTES
# ============================================================================

test: ## Rodar todos os testes
	@echo "🧪 Rodando todos os testes..."
	$(VENV_PYTEST) tests/ -v

test-unit: ## Rodar apenas testes unitários
	@echo "🧪 Rodando testes unitários..."
	$(VENV_PYTEST) tests/unit/ -v

test-integration: ## Rodar testes de integração
	@echo "🧪 Rodando testes de integração..."
	$(VENV_PYTEST) tests/integration/ -v

test-coverage: ## Rodar testes com coverage
	@echo "📊 Rodando testes com coverage..."
	$(VENV_PYTEST) tests/ --cov=modules --cov-report=html --cov-report=term

# ============================================================================
# DOCKER
# ============================================================================

build: ## Build das imagens Docker
	@echo "🔨 Building $(SERVICE_NAME)..."
	$(DOCKER_COMPOSE) build --no-cache

up: ## Subir containers
	@echo "🚀 Iniciando $(SERVICE_NAME)..."
	$(DOCKER_COMPOSE) up -d
	@echo "✅ $(SERVICE_NAME) iniciado!"
	@echo "📊 Verifique: make logs"

down: ## Derrubar containers
	@echo "🛑 Parando $(SERVICE_NAME)..."
	$(DOCKER_COMPOSE) down
	@echo "✅ $(SERVICE_NAME) parado!"

restart: down up ## Reiniciar containers

logs: ## Ver logs do serviço
	@$(DOCKER_COMPOSE) logs -f

ps: ## Listar containers
	@$(DOCKER_COMPOSE) ps

# ============================================================================
# API
# ============================================================================

health: ## Verificar health do serviço
	@echo "🏥 Verificando health..."
	@curl -s $(API_BASE_URL)/health | python3 -m json.tool || echo "❌ Serviço não disponível"

jobs: ## Listar jobs em execução
	@echo "📋 Jobs ativos:"
	@curl -s $(API_BASE_URL)/jobs | python3 -m json.tool || echo "❌ API offline"

status: ## Ver status completo
	@echo "📊 Status do $(SERVICE_NAME):"
	@echo ""
	@echo "Containers:"
	@$(DOCKER_COMPOSE) ps
	@echo ""
	@echo "Health:"
	@curl -s $(API_BASE_URL)/health | python3 -m json.tool 2>/dev/null || echo "❌ API offline"
	@echo ""
	@echo "Jobs:"
	@curl -s $(API_BASE_URL)/jobs 2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Total: {len(data.get(\"jobs\", []))}');" 2>/dev/null || echo "N/A"

# ============================================================================
# MANUTENÇÃO
# ============================================================================

clean: ## Limpar arquivos temporários
	@echo "🧹 Limpando arquivos temporários..."
	rm -rf __pycache__ modules/__pycache__
	rm -rf .pytest_cache
	rm -rf .coverage htmlcov
	@echo "✅ Limpeza concluída!"

clean-all: clean ## Limpar tudo
	@echo "🧹 Limpeza TOTAL..."
	@echo "✅ Limpeza total concluída!"

clean-docker: ## Limpar imagens Docker
	@echo "🧹 Limpando imagens Docker..."
	docker rmi -f $(SERVICE_NAME)-orchestrator 2>/dev/null || true
	@echo "✅ Imagens removidas!"

validate: ## Validar configuração
	@echo "✅ Validando $(SERVICE_NAME)..."
	@echo "Checando docker-compose.yml..."
	@$(DOCKER_COMPOSE) config > /dev/null && echo "✅ docker-compose.yml válido"
	@echo "Checando .env..."
	@test -f .env && echo "✅ .env existe" || echo "⚠️  .env não encontrado"
	@echo "Checando Dockerfile..."
	@test -f Dockerfile && echo "✅ Dockerfile existe" || echo "❌ Dockerfile não encontrado"
	@echo "Checando requirements.txt..."
	@test -f requirements.txt && echo "✅ requirements.txt existe" || echo "❌ requirements.txt não encontrado"
	@echo "Checando main.py..."
	@test -f main.py && echo "✅ main.py existe" || echo "❌ main.py não encontrado"

# ============================================================================
# UTILITÁRIOS
# ============================================================================

shell-container: ## Shell no container
	@docker exec -it $(SERVICE_NAME) /bin/bash

notebook: ## Abrir Jupyter notebook de testes
	@echo "📓 Abrindo notebook..."
	$(VENV_PYTHON) -m jupyter notebook test_orchestrator.ipynb

test-sse: ## Testar SSE (Server-Sent Events) - abre HTML client
	@echo "🌐 Abra test_sse_client.html no navegador"
	@echo "   Arquivo: $(PWD)/test_sse_client.html"
	@which xdg-open > /dev/null && xdg-open test_sse_client.html || echo "Abra manualmente"
