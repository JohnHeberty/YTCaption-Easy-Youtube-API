# ============================================================================
# Makefile - YouTube-Search Service (se6)
# ============================================================================
# Uso: make <target>
# Lista de comandos: make help
# ============================================================================

.PHONY: help
.DEFAULT_GOAL := help

# ============================================================================
# VARIAVEIS
# ============================================================================

DOCKER_COMPOSE := docker compose -f docker/docker-compose.yml
SERVICE_NAME := youtube-search
SERVICE_TITLE := YouTube-Search
PYTHON := python3
VENV := .venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PYTEST := $(VENV_BIN)/pytest
LOG_DIR := ./data/logs
API_BASE_URL := http://localhost:8006
PORT ?= 8006
COMPOSE_FILE := docker/docker-compose.yml
COMPOSE_PROJECT := $(SERVICE_NAME)
CONTAINER_API := $(SERVICE_NAME)-api
CONTAINER_CELERY := $(SERVICE_NAME)-celery-worker
CONTAINER_BEAT := $(SERVICE_NAME)-celery-beat

# ============================================================================
# HELP
# ============================================================================

help: ## Mostrar esta mensagem de ajuda
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║       $(SERVICE_TITLE) Service - Comandos Disponiveis            ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Categorias:"
	@echo "  • Desenvolvimento: venv, install, dev, shell"
	@echo "  • Testes: test, test-unit, test-integration, test-coverage"
	@echo "  • Docker: build, build-nc, up, down, restart, logs, ps, rebuild"
	@echo "  • API: health, status, search, shorts, jobs"
	@echo "  • Celery: celery-logs, celery-restart"
	@echo "  • Beat: beat-logs, beat-restart"
	@echo "  • Manutencao: clean, clean-all, clean-docker, validate"
	@echo "  • Utilitarios: shell-api, shell-celery, shell-beat, fix-permissions, info"
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

logs-celery: ## Ver logs apenas do container Celery worker
	@docker logs -f $(CONTAINER_CELERY)

logs-beat: ## Ver logs apenas do container Celery beat
	@docker logs -f $(CONTAINER_BEAT)

ps: ## Listar containers
	@$(DOCKER_COMPOSE) ps

# ============================================================================
# API
# ============================================================================

health: ## Verificar health do servico
	@echo "Verificando health..."
	@curl -s $(API_BASE_URL)/health | python3 -m json.tool || echo "  Servico nao disponivel"

search: ## Testar busca (use QUERY="termo")
	@echo "Buscando: $(QUERY)"
	@curl -s "$(API_BASE_URL)/search?q=$(QUERY)&limit=5" | python3 -m json.tool

shorts: ## Testar busca de shorts
	@echo "Buscando shorts..."
	@curl -s "$(API_BASE_URL)/shorts?limit=5" | python3 -m json.tool

jobs: ## Listar jobs
	@echo "Jobs:"
	@curl -s $(API_BASE_URL)/jobs | python3 -m json.tool || echo "  API offline"

job: ## Mostrar detalhes de um job (use JOB_ID=...)
	@curl -s $(API_BASE_URL)/jobs/$(JOB_ID) | python3 -m json.tool

status: ## Ver status completo
	@echo "Status do $(SERVICE_TITLE):"
	@echo ""
	@echo "Containers:"
	@$(DOCKER_COMPOSE) ps
	@echo ""
	@echo "Health:"
	@curl -s $(API_BASE_URL)/health | python3 -m json.tool 2>/dev/null || echo "  API offline"

# ============================================================================
# CELERY & BEAT
# ============================================================================

celery-restart: ## Reiniciar Celery worker
	@echo "Reiniciando Celery worker..."
	@docker restart $(CONTAINER_CELERY)
	@echo "  Celery reiniciado!"

beat-restart: ## Reiniciar Celery beat
	@echo "Reiniciando Celery beat..."
	@docker restart $(CONTAINER_BEAT)
	@echo "  Beat reiniciado!"

purge: ## Limpar fila do Celery
	@echo "Limpando fila do Celery..."
	@docker exec $(CONTAINER_CELERY) python -m celery -A app.infrastructure.celery_config.celery_app purge -f 2>/dev/null || \
		echo "  Nao foi possivel limpar fila"

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
	-docker rmi -f $(CONTAINER_API) $(CONTAINER_CELERY) $(CONTAINER_BEAT) 2>/dev/null
	@echo "  Imagens removidas!"

validate: ## Validar configuracao
	@echo "Validando $(SERVICE_TITLE)..."
	@echo -n "  docker-compose.yml: "; $(DOCKER_COMPOSE) config > /dev/null 2>&1 && echo "valido" || echo "invalido"
	@echo -n "  .env:              "; test -f .env && echo "existe" || echo "ausente"
	@echo -n "  Dockerfile:        "; test -f docker/Dockerfile && echo "existe" || echo "ausente"
	@echo -n "  requirements.txt:  "; test -f requirements.txt && echo "existe" || echo "ausente"

info: ## Mostrar informacoes do servico
	@echo "$(SERVICE_TITLE) Service (se6)"
	@echo "  Porta: $(PORT)"
	@echo "  API:   $(API_BASE_URL)"
	@echo "  Docs:  $(API_BASE_URL)/docs"
	@echo "  Diretorio: $(PWD)"
	@echo "  Containers:"
	@echo "    API:    $(CONTAINER_API)"
	@echo "    Celery: $(CONTAINER_CELERY)"
	@echo "    Beat:   $(CONTAINER_BEAT)"

# ============================================================================
# UTILITARIOS
# ============================================================================

shell-api: ## Shell no container da API
	@docker exec -it $(CONTAINER_API) /bin/bash

shell-celery: ## Shell no container do Celery
	@docker exec -it $(CONTAINER_CELERY) /bin/bash

shell-beat: ## Shell no container do Beat
	@docker exec -it $(CONTAINER_BEAT) /bin/bash

fix-permissions: ## Corrigir permissoes dos diretorios
	@echo "Corrigindo permissoes..."
	@mkdir -p $(LOG_DIR)
	-sudo chown -R 1000:1000 $(LOG_DIR) 2>/dev/null
	chmod -R 777 $(LOG_DIR)
	@echo "  Permissoes corrigidas para uid 1000!"
