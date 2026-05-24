# YTCaption-Easy-Youtube-API - Makefile
# Gerenciamento de todos os serviços
# Author: Sistema de Build Automatizado
# Date: 2026-02-22

.PHONY: help install validate clean build up down restart logs status test-syntax test-requirements symlinks
.DEFAULT_GOAL := help

# ==================== VARIÁVEIS ====================
SHELL := /bin/bash
PROJECT_NAME := ytcaption
SERVICES := se1-orchestrator se2-video-downloader se3-audio-normalization se4-audio-transcriber se6-make-video se5-youtube-search

# Build
build: ## Build de todos os serviços
	@echo -e "$(BLUE)Building todos os serviços...$(NC)"
	@docker compose build
	@for service in $(SERVICES); do \
		if [ -f "$(SERVICES_DIR)/$$service/docker-compose.yml" ]; then \
			echo -e "$(YELLOW)  🔨 Building $$service...$(NC)"; \
			docker compose -f $(SERVICES_DIR)/$$service/docker-compose.yml build; \
		fi; \
	done
	@echo -e "$(GREEN)✅ Build concluído!$(NC)"

build-%: ## Build de um serviço específico (ex: make build-se5-youtube-search)
	@service_name=$(subst build-,,$@); \
	if [ -f "$(SERVICES_DIR)/$$service_name/docker-compose.yml" ]; then \
		echo -e "$(YELLOW)🔨 Building $$service_name...$(NC)"; \
		docker compose -f $(SERVICES_DIR)/$$service_name/docker-compose.yml build; \
		echo -e "$(GREEN)✅ $$service_name built!$(NC)"; \
	else \
		echo -e "$(RED)❌ Serviço $$service_name não encontrado$(NC)"; \
		exit 1; \
	fi

build-only-%: ## Build isolado sem subir (ex: make build-only-se3-audio-normalization)
	@service_name=$(subst build-only-,,$@); \
	if [ -f "$(SERVICES_DIR)/$$service_name/docker-compose.yml" ]; then \
		echo -e "$(YELLOW)🔨 Building $$service_name (isolated)...$(NC)"; \
		docker compose -f $(SERVICES_DIR)/$$service_name/docker-compose.yml build --no-cache; \
		echo -e "$(GREEN)✅ $$service_name built successfully!$(NC)"; \
		echo -e "$(BLUE)📊 Use 'make up-$$service_name' para iniciar$(NC)"; \
	else \
		echo -e "$(RED)❌ Serviço $$service_name não encontrado$(NC)"; \
		exit 1; \
	fi

# ==================== UP/DOWN ====================
up: ## Inicia todos os serviços
	@echo -e "$(BLUE)Iniciando todos os serviços...$(NC)"
	@docker compose up -d
	@for service in $(SERVICES); do \
		if [ -f "$(SERVICES_DIR)/$$service/docker-compose.yml" ]; then \
			echo -e "$(YELLOW)  🚀 Iniciando $$service...$(NC)"; \
			docker compose -f $(SERVICES_DIR)/$$service/docker-compose.yml up -d; \
		fi; \
	done
	@echo -e "$(GREEN)✅ Serviços iniciados!$(NC)"
	@$(MAKE) status

up-%: ## Inicia um serviço específico (ex: make up-se5-youtube-search)
	@service_name=$(subst up-,,$@); \
	if [ -f "$(SERVICES_DIR)/$$service_name/docker-compose.yml" ]; then \
		echo -e "$(YELLOW)🚀 Iniciando $$service_name...$(NC)"; \
		docker compose -f $(SERVICES_DIR)/$$service_name/docker-compose.yml up -d; \
		echo -e "$(GREEN)✅ $$service_name iniciado!$(NC)"; \
	else \
		echo -e "$(RED)❌ Serviço $$service_name não encontrado$(NC)"; \
		exit 1; \
	fi

down: ## Para todos os serviços
	@echo -e "$(YELLOW)Parando todos os serviços...$(NC)"
	@for service in $(SERVICES); do \
		if [ -f "$(SERVICES_DIR)/$$service/docker-compose.yml" ]; then \
			echo -e "$(YELLOW)  🛑 Parando $$service...$(NC)"; \
			docker compose -f $(SERVICES_DIR)/$$service/docker-compose.yml down; \
		fi; \
	done
	@docker compose down
	@echo -e "$(GREEN)✅ Serviços parados!$(NC)"

down-%: ## Para um serviço específico (ex: make down-se5-youtube-search)
	@service_name=$(subst down-,,$@); \
	if [ -f "$(SERVICES_DIR)/$$service_name/docker-compose.yml" ]; then \
		echo -e "$(YELLOW)🛑 Parando $$service_name...$(NC)"; \
		docker compose -f $(SERVICES_DIR)/$$service_name/docker-compose.yml down; \
		echo -e "$(GREEN)✅ $$service_name parado!$(NC)"; \
	else \
		echo -e "$(RED)❌ Serviço $$service_name não encontrado$(NC)"; \
		exit 1; \
	fi

restart: down up ## Reinicia todos os serviços

restart-%: ## Reinicia um serviço específico (ex: make restart-se5-youtube-search)
	@service_name=$(subst restart-,,$@); \
	$(MAKE) down-$$service_name; \
	$(MAKE) up-$$service_name

# ==================== LOGS ====================
logs: ## Mostra logs de todos os serviços
	@echo -e "$(BLUE)Logs dos serviços:$(NC)"
	@docker compose logs -f

logs-%: ## Mostra logs de um serviço específico (ex: make logs-se5-youtube-search)
	@service_name=$(subst logs-,,$@); \
	if [ -f "$(SERVICES_DIR)/$$service_name/docker-compose.yml" ]; then \
		echo -e "$(BLUE)Logs de $$service_name:$(NC)"; \
		docker compose -f $(SERVICES_DIR)/$$service_name/docker-compose.yml logs -f; \
	else \
		echo -e "$(RED)❌ Serviço $$service_name não encontrado$(NC)"; \
		exit 1; \
	fi

# ==================== STATUS ====================
status: ## Mostra status de todos os containers
	@echo -e "$(BLUE)═══════════════════════════════════════════════════════════$(NC)"
	@echo -e "$(BLUE)  Status dos Containers$(NC)"
	@echo -e "$(BLUE)═══════════════════════════════════════════════════════════$(NC)"
	@docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "NAME|ytcaption|se5-youtube-search" || echo "Nenhum container encontrado"
	@echo ""

status-%: ## Mostra status de um serviço específico (ex: make status-se5-youtube-search)
	@service_name=$(subst status-,,$@); \
	echo -e "$(BLUE)Status de $$service_name:$(NC)"; \
	docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "NAME|$$service_name" || echo "Serviço não encontrado"

# ==================== LIMPEZA ====================
clean: ## Remove containers, volumes e imagens não utilizadas
	@echo -e "$(YELLOW)⚠️  Limpando containers, volumes e imagens...$(NC)"
	@docker compose down -v --remove-orphans
	@for service in $(SERVICES); do \
		if [ -f "$(SERVICES_DIR)/$$service/docker-compose.yml" ]; then \
			docker compose -f $(SERVICES_DIR)/$$service/docker-compose.yml down -v --remove-orphans; \
		fi; \
	done
	@docker system prune -f
	@echo -e "$(GREEN)✅ Limpeza concluída!$(NC)"

clean-venv: ## Remove ambiente virtual
	@echo -e "$(YELLOW)Removendo ambiente virtual...$(NC)"
	@if [ -d "$(VENV_DIR)" ]; then \
		rm -rf $(VENV_DIR); \
		echo -e "$(GREEN)✅ Ambiente virtual removido$(NC)"; \
	else \
		echo -e "$(YELLOW)⚠️  Ambiente virtual não existe$(NC)"; \
	fi

clean-all: clean clean-venv ## Limpeza completa (containers, volumes, imagens e venv)
	@echo -e "$(GREEN)✅ Limpeza completa concluída!$(NC)"

# ==================== TESTES ====================
test: ## Executa testes básicos de todos os serviços
	@echo -e "$(BLUE)Executando testes...$(NC)"
	@for service in $(SERVICES); do \
		if [ -f "$(SERVICES_DIR)/$$service/tests" ] || [ -f "$(SERVICES_DIR)/$$service/test_*.py" ]; then \
			echo -e "$(YELLOW)  🧪 Testando $$service...$(NC)"; \
			cd $(SERVICES_DIR)/$$service && pytest -v 2>/dev/null || echo -e "$(YELLOW)  ⚠️  Sem testes ou pytest não instalado$(NC)"; \
		fi; \
	done
	@echo -e "$(GREEN)✅ Testes concluídos!$(NC)"

healthcheck: ## Verifica health de todos os serviços em execução
	@echo -e "$(BLUE)Verificando health dos serviços...$(NC)"
	@echo -e "$(YELLOW)  🏥 Youtube Search (porta 8001)...$(NC)"
	@curl -sf http://localhost:8001/health > /dev/null 2>&1 && echo -e "$(GREEN)    ✅ OK$(NC)" || echo -e "$(RED)    ❌ FAIL$(NC)"
	@echo ""

# ==================== GIT ====================
git-status: ## Mostra status do git
	@git status

git-push: ## Faz commit e push das mudanças
	@echo -e "$(YELLOW)Preparando push...$(NC)"
	@git add .
	@git status
	@read -p "Mensagem do commit: " msg; \
	git commit -m "$$msg" || echo -e "$(YELLOW)⚠️  Nada para commitar$(NC)"; \
	git push
	@echo -e "$(GREEN)✅ Push concluído!$(NC)"

# ==================== DESENVOLVIMENTO ====================
dev-setup: symlinks install validate ## Setup completo para desenvolvimento
	@echo -e "$(GREEN)═══════════════════════════════════════════════════════════$(NC)"
	@echo -e "$(GREEN)✅ Setup de desenvolvimento completo!$(NC)"
	@echo -e "$(GREEN)═══════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo -e "$(BLUE)Próximos passos:$(NC)"
	@echo -e "  1. Configure os arquivos .env necessários"
	@echo -e "  2. Execute: make build"
	@echo -e "  3. Execute: make up"
	@echo ""

# ==================== LINT ====================
lint: ## Executa black, isort, flake8, mypy e bandit em todos os serviços
	@echo -e "$(BLUE)═══════════════════════════════════════════════════════════$(NC)"
	@echo -e "$(BLUE)  Linting Projeto$(NC)"
	@echo -e "$(BLUE)═══════════════════════════════════════════════════════════$(NC)"
	@echo -e "$(YELLOW)🔍 black --check --line-length=100 ...$(NC)"
	@if command -v black > /dev/null 2>&1; then \
		black --check --line-length=100 shared/ services/ 2>&1 | tail -5; \
	else \
		echo -e "$(YELLOW)  ⚠️  black não instalado$(NC)"; \
	fi
	@echo -e "$(YELLOW)🔍 isort --check --profile black --line-length 100 ...$(NC)"
	@if command -v isort > /dev/null 2>&1; then \
		isort --check --profile black --line-length 100 shared/ services/ 2>&1 | tail -5; \
	else \
		echo -e "$(YELLOW)  ⚠️  isort não instalado$(NC)"; \
	fi
	@echo -e "$(YELLOW)🔍 flake8 --max-line-length=100 --extend-ignore=E203,E266,E501,W503 --max-complexity=15 ...$(NC)"
	@if command -v flake8 > /dev/null 2>&1; then \
		flake8 --max-line-length=100 --extend-ignore=E203,E266,E501,W503 --max-complexity=15 --exclude=.git,__pycache__,.venv,venv,.trash,migrations shared/ services/ 2>&1 | tail -20; \
	else \
		echo -e "$(YELLOW)  ⚠️  flake8 não instalado$(NC)"; \
	fi
	@echo -e "$(YELLOW)🔍 mypy --ignore-missing-imports ...$(NC)"
	@if command -v mypy > /dev/null 2>&1; then \
		mypy --ignore-missing-imports --no-strict-optional shared/ services/ 2>&1 | tail -10; \
	else \
		echo -e "$(YELLOW)  ⚠️  mypy não instalado$(NC)"; \
	fi
	@echo -e "$(YELLOW)🔍 bandit -r ...$(NC)"
	@if command -v bandit > /dev/null 2>&1; then \
		bandit -r shared/ services/ -c .bandit.yml 2>&1 | tail -10; \
	else \
		echo -e "$(YELLOW)  ⚠️  bandit não instalado$(NC)"; \
	fi
	@echo -e "$(GREEN)✅ Lint concluído!$(NC)"

# ==================== TEST-CI ====================
test-ci: ## Executa testes rápidos para CI (exclui slow, integration, e2e)
	@echo -e "$(BLUE)═══════════════════════════════════════════════════════════$(NC)"
	@echo -e "$(BLUE)  Running CI Tests (unit only, no slow/integration/e2e)$(NC)"
	@echo -e "$(BLUE)═══════════════════════════════════════════════════════════$(NC)"
	@for service in $(SERVICES); do \
		if [ -d "$(SERVICES_DIR)/$$service/tests" ] || [ -d "$(SERVICES_DIR)/$$service/app" ]; then \
			echo -e "$(YELLOW)  🧪 Testing $$service...$(NC)"; \
			cd $(SERVICES_DIR)/$$service && pytest -x -m "not slow and not integration and not e2e" -q 2>/dev/null || echo -e "$(YELLOW)  ⚠️  $$service: sem testes ou pytest não instalado$(NC)"; \
			cd - > /dev/null; \
		fi; \
	done
	@echo -e "$(GREEN)✅ CI Tests concluídos!$(NC)"

# ==================== INFORMAÇÕES ====================
list-services: ## Lista todos os serviços disponíveis
	@echo -e "$(BLUE)Serviços disponíveis:$(NC)"
	@for service in $(SERVICES); do \
		echo -e "  $(GREEN)•$(NC) $(SERVICES_DIR)/$$service"; \
	done

check-ports: ## Verifica portas em uso
	@echo -e "$(BLUE)Portas em uso pelos serviços:$(NC)"
	@netstat -tuln | grep -E "8001|8002|8003|8004|8005" || echo "Nenhuma porta dos serviços em uso"

check-port-conflicts: ## Verifica conflitos de portas dos serviços
	@echo -e "$(BLUE)═══════════════════════════════════════════════════════════$(NC)"
	@echo -e "$(BLUE)  Verificando Conflitos de Portas$(NC)"
	@echo -e "$(BLUE)═══════════════════════════════════════════════════════════$(NC)"
	@echo -e "$(YELLOW)Serviços e suas portas configuradas:$(NC)"
	@for service in $(SERVICES); do \
		if [ -f "$(SERVICES_DIR)/$$service/.env" ]; then \
			port=$$(grep "^PORT=" $(SERVICES_DIR)/$$service/.env | cut -d= -f2); \
			if [ -n "$$port" ]; then \
				echo -e "  $(GREEN)•$(NC) $$service: porta $$port"; \
			fi; \
		fi; \
	done
	@echo ""
	@echo -e "$(YELLOW)Containers em execução:$(NC)"
	@docker ps --format "table {{.Names}}\t{{.Ports}}" | grep -E "NAME|audio|youtube|video|make" || echo "Nenhum container em execução"

stop-port-%: ## Para container usando porta específica (ex: make stop-port-8002)
	@port=$(subst stop-port-,,$@); \
	echo -e "$(YELLOW)🛑 Parando container na porta $$port...$(NC)"; \
	container_id=$$(docker ps --format "{{.ID}}" --filter "publish=$$port"); \
	if [ -n "$$container_id" ]; then \
		docker stop $$container_id; \
		echo -e "$(GREEN)✅ Container parado$(NC)"; \
	else \
		echo -e "$(RED)❌ Nenhum container encontrado na porta $$port$(NC)"; \
	fi

docker-info: ## Mostra informações do Docker
	@echo -e "$(BLUE)Informações do Docker:$(NC)"
	@docker --version
	@docker compose --version
	@echo ""
	@echo -e "$(BLUE)Espaço em disco:$(NC)"
	@docker system df
