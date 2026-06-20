# ============================================================================
# Makefile - Make-Video-IMG Service (se9)
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
SERVICE_NAME := se9-make-video-img
SERVICE_TITLE := Make-Video-IMG
PYTHON := python3
VENV := .venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PYTEST := $(VENV_BIN)/pytest
LOG_DIR := ./data/logs
API_BASE_URL := http://localhost:8009
PORT ?= 8009
COMPOSE_FILE := docker/docker-compose.yml
COMPOSE_PROJECT := $(SERVICE_NAME)
CONTAINER_API := $(SERVICE_NAME)-api

# ============================================================================
# HELP
# ============================================================================

help: ## Mostrar esta mensagem de ajuda
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║      $(SERVICE_TITLE) Service - Comandos Disponiveis             ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
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
	$(VENV_PYTEST) tests/ --cov=app --cov-report=html --cov-report=term

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

logs-api: ## Ver logs apenas do container API
	@docker logs -f $(CONTAINER_API)

ps: ## Listar containers
	@$(DOCKER_COMPOSE) ps

# ============================================================================
# API
# ============================================================================

health: ## Verificar health do servico
	@echo "Verificando health..."
	@curl -s $(API_BASE_URL)/health | python3 -m json.tool || echo "  Servico nao disponivel"

status: ## Ver status completo
	@echo "Status do $(SERVICE_TITLE):"
	@echo ""
	@echo "Containers:"
	@$(DOCKER_COMPOSE) ps
	@echo ""
	@echo "Health:"
	@curl -s $(API_BASE_URL)/health | python3 -m json.tool 2>/dev/null || echo "  API offline"

# ============================================================================
# MANUTENCAO
# ============================================================================

clean: ## Limpar arquivos temporarios
	@echo "Limpando arquivos temporarios..."
	rm -rf __pycache__ app/__pycache__
	rm -rf .pytest_cache
	rm -rf .coverage htmlcov
	rm -rf data/temp/* data/outputs/*
	@echo "  Limpeza concluida!"

clean-all: clean ## Limpar tudo (incluindo logs)
	@echo "Limpeza TOTAL..."
	rm -f $(LOG_DIR)/*.log $(LOG_DIR)/*.json
	@echo "  Limpeza total concluida!"

clean-docker: ## Limpar imagens Docker
	@echo "Limpando imagens Docker..."
	-docker rmi -f $(CONTAINER_API) 2>/dev/null
	@echo "  Imagens removidas!"

validate: ## Validar configuracao
	@echo "Validando $(SERVICE_TITLE)..."
	@echo -n "  docker-compose.yml: "; $(DOCKER_COMPOSE) config > /dev/null 2>&1 && echo "valido" || echo "invalido"
	@echo -n "  .env:               "; test -f .env && echo "existe" || echo "ausente"
	@echo -n "  Dockerfile:         "; test -f docker/Dockerfile && echo "existe" || echo "ausente"
	@echo -n "  requirements.txt:   "; test -f requirements.txt && echo "existe" || echo "ausente"

info: ## Mostrar informacoes do servico
	@echo "$(SERVICE_TITLE) Service (se9)"
	@echo "  Porta: $(PORT)"
	@echo "  API:   $(API_BASE_URL)"
	@echo "  Diretorio: $(PWD)"
	@echo "  Container: $(CONTAINER_API)"

# ============================================================================
# UTILITARIOS
# ============================================================================

shell-api: ## Shell no container da API
	@docker exec -it $(CONTAINER_API) /bin/bash

fix-permissions: ## Corrigir permissoes dos diretorios
	@echo "Corrigindo permissoes..."
	@mkdir -p $(LOG_DIR) data/temp data/outputs
	-sudo chown -R 1000:1000 $(LOG_DIR) data/temp data/outputs 2>/dev/null
	chmod -R 777 $(LOG_DIR) data/temp data/outputs
	@echo "  Permissoes corrigidas para uid 1000!"
