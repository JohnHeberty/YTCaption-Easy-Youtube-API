# ============================================================================
# Makefile - Orchestrator Service (se1)
# ============================================================================
# Uso: make <target>
# Lista de comandos: make help
# ============================================================================

.PHONY: help
.DEFAULT_GOAL := help

# ============================================================================
# VARIAVEIS
# ============================================================================

DOCKER_COMPOSE := docker compose -f docker/docker-compose.yml --env-file .env
SERVICE_NAME := orchestrator
SERVICE_TITLE := Orchestrator
PYTHON := python3
VENV := .venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PYTEST := $(VENV_BIN)/pytest
LOG_DIR := ./logs
API_BASE_URL := http://localhost:8001
PORT ?= 8001
COMPOSE_FILE := docker/docker-compose.yml
COMPOSE_PROJECT := $(SERVICE_NAME)

# ============================================================================
# HELP
# ============================================================================

help: ## Mostrar esta mensagem de ajuda
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║         $(SERVICE_TITLE) Service - Comandos Disponiveis           ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Categorias:"
	@echo "  • Desenvolvimento: venv, install, dev, shell"
	@echo "  • Testes: test, test-unit, test-integration, test-coverage"
	@echo "  • Docker: build, build-nc, up, down, restart, logs, ps, rebuild"
	@echo "  • API: health, status, jobs"
	@echo "  • Manutencao: clean, clean-all, clean-docker, validate"
	@echo "  • Utilitarios: shell-container, info"
	@echo ""

# ============================================================================
# DESENVOLVIMENTO
# ============================================================================

venv: ## Criar virtual environment (.venv)
	@echo "Criando virtual environment..."
	@if [ ! -d "$(VENV)" ]; then \
		$(PYTHON) -m venv $(VENV); \
		echo "  Virtual environment criado: $(VENV)"; \
		echo "  Ativar: source $(VENV)/bin/activate"; \
	else \
		echo "  Virtual environment ja existe: $(VENV)"; \
	fi

install: venv ## Instalar dependencias Python no venv
	@echo "Instalando dependencias no venv..."
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements.txt
	@echo "  Dependencias instaladas!"

dev: ## Rodar servico em modo desenvolvimento (local, sem Docker)
	@echo "Iniciando $(SERVICE_TITLE) em modo dev..."
	@echo "   Port: $(PORT)"
	PORT=$(PORT) $(VENV_PYTHON) run.py

shell: ## Abrir shell Python com ambiente configurado
	@echo "Abrindo Python shell..."
	$(VENV_PYTHON)

# ============================================================================
# TESTES
# ============================================================================

test: ## Rodar todos os testes
	@echo "Rodando todos os testes..."
	$(VENV_PYTEST) tests/ -v

test-unit: ## Rodar apenas testes unitarios
	@echo "Rodando testes unitarios..."
	$(VENV_PYTEST) tests/unit/ -v || $(VENV_PYTEST) tests/ -v -m unit

test-integration: ## Rodar testes de integracao
	@echo "Rodando testes de integracao..."
	$(VENV_PYTEST) tests/integration/ -v || $(VENV_PYTEST) tests/ -v -m integration

test-coverage: ## Rodar testes com coverage
	@echo "Rodando testes com coverage..."
	$(VENV_PYTEST) tests/ --cov=modules --cov=app --cov-report=html --cov-report=term

# ============================================================================
# DOCKER
# ============================================================================

build: ## Build das imagens Docker
	@echo "Building $(SERVICE_TITLE)..."
	$(DOCKER_COMPOSE) build

build-nc: ## Build das imagens Docker sem cache
	@echo "Building $(SERVICE_TITLE) (no cache)..."
	$(DOCKER_COMPOSE) build --no-cache

up: ## Subir containers
	@echo "Iniciando $(SERVICE_TITLE)..."
	$(DOCKER_COMPOSE) up -d
	@echo "  $(SERVICE_TITLE) iniciado!"
	@echo "  Verifique: make logs"

down: ## Derrubar containers
	@echo "Parando $(SERVICE_TITLE)..."
	$(DOCKER_COMPOSE) down
	@echo "  $(SERVICE_TITLE) parado!"

restart: down up ## Reiniciar containers

rebuild: build-nc up ## Rebuild completo sem cache + iniciar

logs: ## Ver logs do servico
	@$(DOCKER_COMPOSE) logs -f

ps: ## Listar containers
	@$(DOCKER_COMPOSE) ps

# ============================================================================
# API
# ============================================================================

health: ## Verificar health do servico
	@echo "Verificando health..."
	@curl -s $(API_BASE_URL)/health | python3 -m json.tool || echo "  Servico nao disponivel"

jobs: ## Listar jobs em execucao
	@echo "Jobs ativos:"
	@curl -s $(API_BASE_URL)/jobs | python3 -m json.tool || echo "  API offline"

job: ## Mostrar detalhes de um job (use JOB_ID=...)
	@echo "Job: $(JOB_ID)"
	@curl -s $(API_BASE_URL)/jobs/$(JOB_ID) | python3 -m json.tool || echo "  Job nao encontrado"

status: ## Ver status completo
	@echo "Status do $(SERVICE_TITLE):"
	@echo ""
	@echo "Containers:"
	@$(DOCKER_COMPOSE) ps
	@echo ""
	@echo "Health:"
	@curl -s $(API_BASE_URL)/health | python3 -m json.tool 2>/dev/null || echo "  API offline"
	@echo ""
	@echo "Jobs:"
	@curl -s $(API_BASE_URL)/jobs 2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'  Total: {len(data.get(\"jobs\", []))}')" 2>/dev/null || echo "  N/A"

# ============================================================================
# MANUTENCAO
# ============================================================================

clean: ## Limpar arquivos temporarios
	@echo "Limpando arquivos temporarios..."
	rm -rf __pycache__ app/__pycache__
	rm -rf .pytest_cache
	rm -rf .coverage htmlcov
	@echo "  Limpeza concluida!"

clean-all: clean ## Limpar tudo (incluindo logs)
	@echo "Limpeza TOTAL..."
	rm -f $(LOG_DIR)/*.log $(LOG_DIR)/*.json
	@echo "  Limpeza total concluida!"

clean-docker: ## Limpar imagens Docker
	@echo "Limpando imagens Docker..."
	-docker rmi -f $(COMPOSE_PROJECT)-$(SERVICE_NAME) 2>/dev/null
	@echo "  Imagens removidas!"

validate: ## Validar configuracao
	@echo "Validando $(SERVICE_TITLE)..."
	@echo -n "  docker-compose.yml: "; $(DOCKER_COMPOSE) config > /dev/null 2>&1 && echo "valido" || echo "invalido"
	@echo -n "  .env:              "; test -f .env && echo "existe" || echo "ausente"
	@echo -n "  Dockerfile:        "; test -f docker/Dockerfile && echo "existe" || echo "ausente"
	@echo -n "  requirements.txt:  "; test -f requirements.txt && echo "existe" || echo "ausente"

info: ## Mostrar informacoes do servico
	@echo "$(SERVICE_TITLE) Service (se1)"
	@echo "  Porta: $(PORT)"
	@echo "  API:   $(API_BASE_URL)"
	@echo "  Diretorio: $(PWD)"
	@echo "  Containers: ytcaption-$(SERVICE_NAME)"

# ============================================================================
# UTILITARIOS
# ============================================================================

shell-container: ## Shell no container da API
	@docker exec -it ytcaption-$(SERVICE_NAME) /bin/bash
