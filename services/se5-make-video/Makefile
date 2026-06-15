# ============================================================================
# Makefile - Make-Video Service
# ============================================================================
# Comandos padronizados para desenvolvimento, testes, calibração e deploy
# 
# Uso: make <target>
# Lista de comandos: make help
# ============================================================================

.PHONY: help
.DEFAULT_GOAL := help

# ============================================================================
# VARIÁVEIS
# ============================================================================

DOCKER_COMPOSE := docker compose -f docker/docker-compose.yml --env-file .env
DOCKER_SERVICE := make-video
PYTHON := python3
VENV := .venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PYTEST := $(VENV_BIN)/pytest
DATA_DIR := ./data
RAW_DIR := $(DATA_DIR)/raw
TRANSFORM_DIR := $(DATA_DIR)/transform
VALIDATE_DIR := $(DATA_DIR)/validate
APPROVED_DIR := $(DATA_DIR)/approved
CALIBRATION_DIR := $(DATA_DIR)/calibration
LOG_DIR := /tmp
API_BASE_URL := http://localhost:8005
API_QUERY ?= Videos Satisfatorios
API_MAX_SHORTS ?= 20
API_LIMIT ?= 50
API_STATUS ?=
DAYS ?= 30
DEEP ?= false
PURGE_CELERY_QUEUE ?= false
MAX_AGE_MINUTES ?= 30
MARK_AS_FAILED ?= true

# Configurações de calibração
OPTUNA_TRIALS := 100
OPTUNA_TIMEOUT := 7200
ORPHAN_THRESHOLD := 5

# ============================================================================
# HELP
# ============================================================================

help: ## Mostrar esta mensagem de ajuda
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║         Make-Video Service - Comandos Disponíveis              ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "📚 Categorias:"
	@echo "  • Desenvolvimento: install, venv, dev, logs, shell"
	@echo "  • Testes: test, test-all, test-quick, test-unit, test-integration, test-e2e"
	@echo "  • Validação: test-validate, test-sprint, test-coverage"
	@echo "  • Compatibilização: compatibility, compatibility-check"
	@echo "  • API Controle: api-health, api-download, api-jobs, api-admin-stats"
	@echo "  • Calibração: calibrate-start, calibrate-status, calibrate-watch, calibrate-logs"
	@echo "  • Deployment: network, build, up, down, restart"
	@echo "  • Manutenção: clean, clean-all, validate"
	@echo ""
	@echo "🎯 Fluxo de Testes:"
	@echo "  1. make test              → Todos os testes (379 tests)"
	@echo "  2. make test-unit         → Apenas unit tests (~255 tests)"
	@echo "  3. make test-integration  → Apenas integration tests (~74 tests)"
	@echo "  4. make test-e2e          → Apenas e2e tests (~50 tests)"
	@echo "  5. make test-validate     → Validação completa (zero mocks, zero skips)"
	@echo ""
	@echo "🎯 Fluxo de Calibração:"
	@echo "  1. make calibrate-start     → Iniciar em background"
	@echo "  2. make calibrate-watch     → Acompanhar em tempo real"
	@echo "  3. make calibrate-status    → Ver status atual"
	@echo "  4. make calibrate-apply     → Aplicar melhor threshold"
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
	@echo "✅ Dependências instaladas no $(VENV)"
	@echo "💡 Ativar venv: source $(VENV)/bin/activate"

dev: ## Iniciar serviço em modo desenvolvimento
	@echo "🚀 Iniciando em modo desenvolvimento..."
	$(DOCKER_COMPOSE) up --build

logs: ## Ver logs do serviço em tempo real
	$(DOCKER_COMPOSE) logs -f $(DOCKER_SERVICE)

shell: ## Abrir shell interativo no container
	$(DOCKER_COMPOSE) run --rm $(DOCKER_SERVICE) /bin/bash

# ============================================================================
# TESTES
# ============================================================================

test: ## Executar todos os testes (379 tests)
	@echo "🧪 Executando TODOS os testes..."
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@$(VENV_PYTEST) tests/ -v --tb=short || (echo "❌ Testes falharam" && exit 1)
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "✅ Todos os testes passaram!"

test-all: test ## Alias para 'make test'

test-quick: ## Executar testes rápidos (sem slow tests)
	@echo "⚡ Executando testes rápidos..."
	@$(VENV_PYTEST) tests/ -v -m "not slow" --tb=short

test-unit: ## Executar apenas testes unitários (~255 tests)
	@echo "🔬 Executando testes unitários..."
	@$(VENV_PYTEST) tests/unit/ -v --tb=short

test-integration: ## Executar apenas testes de integração (~74 tests)
	@echo "🔗 Executando testes de integração..."
	@$(VENV_PYTEST) tests/integration/ -v --tb=short

test-e2e: ## Executar apenas testes e2e (~50 tests)
	@echo "🌐 Executando testes end-to-end..."
	@$(VENV_PYTEST) tests/e2e/ -v --tb=short

test-setup: ## Executar testes de setup/validação
	@echo "⚙️  Executando testes de setup..."
	@$(VENV_PYTEST) tests/test_setup_validation.py tests/test_00_setup_validation.py -v

test-sprint: ## Executar testes por sprint (use SPRINT=X)
	@if [ -z "$(SPRINT)" ]; then \
		echo "❌ Use: make test-sprint SPRINT=<número>"; \
		echo "Exemplo: make test-sprint SPRINT=10"; \
		exit 1; \
	fi
	@echo "🎯 Executando testes da Sprint $(SPRINT)..."
	@case "$(SPRINT)" in \
		0|1) $(VENV_PYTEST) tests/test_*setup*.py tests/unit/core/ -v ;; \
		2) $(VENV_PYTEST) tests/unit/shared/ -v ;; \
		3) $(VENV_PYTEST) tests/unit/utils/ -v ;; \
		4) $(VENV_PYTEST) tests/unit/infrastructure/ -v ;; \
		5) $(VENV_PYTEST) tests/unit/video_processing/ tests/integration/video_processing/ -v ;; \
		6) $(VENV_PYTEST) tests/unit/subtitle_processing/ tests/integration/subtitle_processing/ -v ;; \
		7) $(VENV_PYTEST) tests/unit/services/ tests/integration/services/ -v ;; \
		8) $(VENV_PYTEST) tests/integration/pipeline/ -v ;; \
		9) $(VENV_PYTEST) tests/unit/domain/ tests/integration/domain/ -v ;; \
		10) $(VENV_PYTEST) tests/e2e/ -v ;; \
		*) echo "❌ Sprint válidas: 0-10"; exit 1 ;; \
	esac

test-coverage: ## Executar testes com cobertura
	@echo "📊 Executando testes com cobertura..."
	@$(VENV_PYTEST) tests/ --cov=app --cov-report=html --cov-report=term
	@echo ""
	@echo "📄 Relatório HTML gerado: htmlcov/index.html"

test-validate: ## Validação completa: zero mocks, zero skips, 100% pass
	@echo "✅ VALIDAÇÃO COMPLETA DE TESTES"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "📊 Coletando testes..."
	@TOTAL=$$($(VENV_PYTEST) tests/ --collect-only -q 2>&1 | tail -1 | grep -oE '[0-9]+' | head -1); \
	echo "   Total: $$TOTAL testes"; \
	echo ""
	@echo "🔍 Verificando mocks..."
	@MOCKS=$$(find tests/ -name "*.py" -exec grep -l "Mock\|@patch\|MagicMock" {} \; 2>/dev/null | wc -l); \
	if [ $$MOCKS -eq 0 ]; then \
		echo "   ✅ Zero mocks encontrados"; \
	else \
		echo "   ❌ $$MOCKS arquivos com mocks encontrados!"; \
		exit 1; \
	fi
	@echo ""
	@echo "🧪 Executando todos os testes..."
	@$(VENV_PYTEST) tests/ -v --tb=short > /tmp/test_validation.txt 2>&1 || (cat /tmp/test_validation.txt && exit 1)
	@echo ""
	@echo "📈 Analisando resultados..."
	@PASSED=$$(grep -E "passed" /tmp/test_validation.txt | tail -1 | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+'); \
	FAILED=$$(grep -E "failed" /tmp/test_validation.txt | tail -1 | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' || echo 0); \
	SKIPPED=$$(grep -E "skipped" /tmp/test_validation.txt | tail -1 | grep -oE '[0-9]+ skipped' | grep -oE '[0-9]+' || echo 0); \
	echo "   Passed:  $$PASSED"; \
	echo "   Failed:  $$FAILED"; \
	echo "   Skipped: $$SKIPPED"; \
	echo ""; \
	if [ $$FAILED -gt 0 ]; then \
		echo "   ❌ Testes falhando!"; \
		exit 1; \
	fi; \
	if [ $$SKIPPED -gt 0 ]; then \
		echo "   ❌ Testes sendo pulados!"; \
		exit 1; \
	fi; \
	echo "   ✅ 100% dos testes passando"; \
	echo "   ✅ Zero skips"; \
	echo "   ✅ Zero mocks"
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "🎉 VALIDAÇÃO COMPLETA: SUCESSO!"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test-validate-exception-fix: ## Validar correção do bug Exception Details Conflict
	@echo "🔍 Validando correção do bug de Exception Details Conflict..."
	@$(VENV_PYTHON) validate_exception_fix.py

test-no-mocks: ## Verificar que não há mocks nos testes
	@echo "🔍 Verificando ausência de mocks..."
	@MOCKS=$$(find tests/ -name "*.py" -exec grep -l "Mock\|@patch\|MagicMock" {} \; 2>/dev/null); \
	if [ -z "$$MOCKS" ]; then \
		echo "✅ Nenhum mock encontrado (100% real)"; \
	else \
		echo "❌ Mocks encontrados em:"; \
		echo "$$MOCKS"; \
		exit 1; \
	fi

test-count: ## Contar testes por categoria
	@echo "📊 Contagem de Testes"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Unit Tests:"
	@$(VENV_PYTEST) tests/unit/ --collect-only -q 2>&1 | tail -1
	@echo ""
	@echo "Integration Tests:"
	@$(VENV_PYTEST) tests/integration/ --collect-only -q 2>&1 | tail -1
	@echo ""
	@echo "E2E Tests:"
	@$(VENV_PYTEST) tests/e2e/ --collect-only -q 2>&1 | tail -1
	@echo ""
	@echo "Total:"
	@$(VENV_PYTEST) tests/ --collect-only -q 2>&1 | tail -1
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test-imports: ## Validar todos os imports críticos
	@echo "🔍 Validando imports..."
	@$(VENV_PYTHON) -c "from app.video_processing.video_validator import VideoValidator; print('✅ VideoValidator')"
	@$(VENV_PYTHON) -c "from app.video_processing.ocr_detector import get_ocr_detector; print('✅ get_ocr_detector')"
	@$(VENV_PYTHON) -c "from app.infrastructure.celery_tasks import recover_orphaned_jobs; print('✅ celery_tasks')"
	@$(VENV_PYTHON) -c "from app.main import app; print('✅ FastAPI app')"
	@echo "✅ Todos os imports funcionando"

test-critical: ## Executar apenas testes críticos (CRON, bug fixes)
	@echo "🔴 Executando testes críticos..."
	@$(VENV_PYTEST) tests/unit/core/test_config.py::TestGetSettings::test_get_settings_has_pipeline_directory_keys -v
	@$(VENV_PYTEST) tests/integration/pipeline/test_video_pipeline.py::TestCleanupOrphanedFiles::test_cleanup_orphaned_files_no_keyerror -v
	@$(VENV_PYTEST) tests/e2e/test_main_application.py::TestCronJobs::test_cleanup_cron_does_not_crash -v
	@echo "✅ Todos os testes críticos passaram!"

# ============================================================================
# CALIBRAÇÃO OCR
# ============================================================================

calibrate: calibrate-start ## Executar calibração completa (100 trials, ~60-80h)

calibrate-start: ## Iniciar calibração em background
	@if docker ps --format "{{.Names}}" | grep -qE "calibrate|optuna|make-video-run"; then \
		echo "⚠️  Calibração já está rodando!"; \
		echo "Para ver status: make calibrate-status"; \
		exit 1; \
	fi
	@echo "🎯 Iniciando Calibração PaddleOCR"
	@echo "⚠️  Duração estimada: 60-80 horas"
	@echo "⚠️  Trials: $(OPTUNA_TRIALS)"
	@echo ""
	@echo "🚀 Iniciando..."
	@$(DOCKER_COMPOSE) run -d --rm --name calibrate_trsd_optuna \
		-v "$$(pwd)/data:/app/data:rw" \
		$(DOCKER_SERVICE) python calibrate_trsd_optuna.py
	@sleep 3
	@CONTAINER=$$(docker ps --filter "name=calibrate" --format "{{.ID}}" | head -1); \
	if [ -n "$$CONTAINER" ]; then \
		date '+%Y-%m-%d %H:%M:%S' > $(LOG_DIR)/calibration_start.txt; \
		echo ""; \
		echo "✅ Calibração iniciada!"; \
		echo "   Container: $$CONTAINER"; \
		echo ""; \
		echo "📋 Comandos úteis:"; \
		echo "   make cal-status  → Ver status"; \
		echo "   make cal-logs    → Ver logs"; \
		echo "   make cal-watch   → Monitorar"; \
		echo "   make cal-stop    → Parar"; \
	else \
		echo "❌ Erro ao iniciar calibração"; \
		docker logs calibrate_trsd_optuna 2>&1 | tail -20; \
		exit 1; \
	fi

calibrate-quick: ## Executar calibração rápida (5 trials, ~3-4h)
	@echo "⚡ Iniciando calibração RÁPIDA (validação)..."
	@echo "⚠️  Duração estimada: 3-4 horas"
	$(DOCKER_COMPOSE) run --rm \
		-v "$$(pwd):/app:ro" \
		-v "$$(pwd)/data:/app/data:rw" \
		-e OPTUNA_TRIALS=5 \
		-e OPTUNA_TIMEOUT=600 \
		$(DOCKER_SERVICE) python calibrate_trsd_optuna.py

calibrate-status: ## Monitorar status da calibração
	@echo "📊 Status da Calibração OCR - PaddleOCR"
	@echo "═══════════════════════════════════════════════════════════"
	@CONTAINERS=$$(docker ps --format "{{.Names}}	{{.Status}}	{{.ID}}" 2>/dev/null | grep -E "calibrate|optuna|make-video-run"); \
	if [ -n "$$CONTAINERS" ]; then \
		echo "✅ CALIBRAÇÃO ATIVA:"; \
		echo ""; \
		NAME=$$(echo "$$CONTAINERS" | head -1 | cut -f1); \
		STATUS=$$(echo "$$CONTAINERS" | head -1 | cut -f2); \
		ID=$$(echo "$$CONTAINERS" | head -1 | cut -f3); \
		echo "   🐳 Container: $$NAME"; \
		echo "   📍 ID: $$ID"; \
		echo "   ⏰ Status: $$STATUS"; \
		echo ""; \
		STATS=$$(docker stats --no-stream --format "{{.CPUPerc}}	{{.MemUsage}}" $$ID 2>/dev/null); \
		if [ -n "$$STATS" ]; then \
			CPU=$$(echo "$$STATS" | cut -f1); \
			MEM=$$(echo "$$STATS" | cut -f2); \
			echo "   💻 CPU: $$CPU"; \
			echo "   🧠 Memória: $$MEM"; \
		fi; \
		echo ""; \
		LOGS=$$(docker logs $$ID 2>&1 | grep "Trial.*finished" | tail -3); \
		if [ -n "$$LOGS" ]; then \
			echo "   📈 Últimos 3 trials:"; \
			echo "$$LOGS" | sed 's/^/      /'; \
		else \
			echo "   ⏳ Carregando modelos PaddleOCR..."; \
		fi; \
		if [ -f $(LOG_DIR)/calibration_start.txt ]; then \
			START=$$(cat $(LOG_DIR)/calibration_start.txt); \
			echo ""; \
			echo "   🕐 Iniciado: $$START"; \
			START_SEC=$$(date -d "$$START" +%s 2>/dev/null || echo 0); \
			NOW_SEC=$$(date +%s); \
			if [ $$START_SEC -gt 0 ]; then \
				ELAPSED=$$((NOW_SEC - START_SEC)); \
				HOURS=$$((ELAPSED / 3600)); \
				MINS=$$(((ELAPSED % 3600) / 60)); \
				echo "   ⏱️  Decorrido: $${HOURS}h $${MINS}m"; \
			fi; \
		fi; \
	else \
		echo "❌ NENHUMA CALIBRAÇÃO RODANDO"; \
		echo ""; \
		echo "💡 Para iniciar:"; \
		echo "   make calibrate-start  (100 trials, ~60-80h)"; \
		echo "   make calibrate-quick  (5 trials, ~3-4h)"; \
	fi
	@echo ""
	@if [ -f $(CALIBRATION_DIR)/trsd_optuna_best_params.json ]; then \
		echo "🎯 Melhor resultado:"; \
		grep -E "min_confidence|best_accuracy|n_trials" $(CALIBRATION_DIR)/trsd_optuna_best_params.json | head -5; \
	fi
	@echo "═══════════════════════════════════════════════════════════"

calibrate-logs: ## Ver logs da calibração em tempo real
	@CONTAINER=$$(docker ps --format "{{.ID}}" 2>/dev/null | head -1); \
	CALCONTAINER=$$(docker ps --format "{{.Names}}	{{.ID}}" | grep -E "calibrate|optuna|make-video-run" | head -1 | cut -f2); \
	if [ -n "$$CALCONTAINER" ]; then \
		echo "📋 Logs em tempo real (Ctrl+C para sair)"; \
		echo "Container: $$CALCONTAINER"; \
		echo "═══════════════════════════════════════════════════════════"; \
		docker logs -f $$CALCONTAINER 2>&1; \
	else \
		echo "❌ Calibração não está rodando"; \
		echo "💡 Para iniciar: make calibrate-start"; \
	fi

calibrate-watch: ## Monitorar status continuamente (atualiza a cada 30s)
	@echo "👁️  Monitoramento contínuo (Ctrl+C para sair)"
	@echo "Atualizando a cada 30 segundos..."
	@echo ""
	@while true; do \
		clear; \
		make calibrate-status; \
		echo ""; \
		echo "🔄 Próxima atualização em 30s... (Ctrl+C para sair)"; \
		sleep 30; \
	done

calibrate-stop: ## Parar calibração em execução
	@echo "🛑 Parando calibração..."
	@CONTAINERS=$$(docker ps --format "{{.Names}}	{{.ID}}" | grep -E "calibrate|optuna" | cut -f2); \
	if [ -z "$$CONTAINERS" ]; then \
		CONTAINERS=$$(docker ps --format "{{.Names}}	{{.ID}}" | grep "make-video-run" | cut -f2); \
	fi; \
	if [ -n "$$CONTAINERS" ]; then \
		for CID in $$CONTAINERS; do \
			echo "  Parando container: $$CID"; \
			docker stop $$CID 2>/dev/null; \
		done; \
		rm -f $(LOG_DIR)/calibration_start.txt 2>/dev/null; \
		echo "✅ Calibração interrompida"; \
	else \
		echo "❌ Nenhuma calibração em execução"; \
	fi

calibrate-clean: ## Limpar logs e PIDs de calibração
	@echo "🧹 Limpando arquivos de calibração..."
	@rm -f $(LOG_DIR)/calibration.pid
	@rm -f $(LOG_DIR)/calibration_start.txt
	@rm -f $(LOG_DIR)/optuna_full.log
	@echo "✅ Limpeza concluída"
	@echo "⚠️  Resultados em data/calibration/ foram preservados"

calibrate-apply: ## Aplicar melhor threshold encontrado ao .env
	@if [ -f $(CALIBRATION_DIR)/trsd_optuna_best_params.json ]; then \
		BEST_THRESHOLD=$$(cat $(CALIBRATION_DIR)/trsd_optuna_best_params.json | jq -r '.best_params.min_confidence'); \
		echo "🎯 Melhor threshold encontrado: $$BEST_THRESHOLD"; \
		if grep -q "OCR_CONFIDENCE_THRESHOLD=" .env 2>/dev/null; then \
			sed -i "s/OCR_CONFIDENCE_THRESHOLD=.*/OCR_CONFIDENCE_THRESHOLD=$$BEST_THRESHOLD/" .env; \
			echo "✅ .env atualizado"; \
		else \
			echo "OCR_CONFIDENCE_THRESHOLD=$$BEST_THRESHOLD" >> .env; \
			echo "✅ .env atualizado"; \
		fi; \
		echo "⚠️  Necessário reiniciar: make restart"; \
	else \
		echo "❌ Nenhum resultado de calibração encontrado"; \
		echo "💡 Executar calibração primeiro: make calibrate"; \
	fi

calibrate-report: ## Mostrar relatório completo da calibração
	@if [ -f $(CALIBRATION_DIR)/trsd_optuna_report.md ]; then \
		cat $(CALIBRATION_DIR)/trsd_optuna_report.md; \
	else \
		echo "❌ Relatório não encontrado"; \
		echo "💡 Executar calibração primeiro: make calibrate-start"; \
	fi

calibrate-results: ## Mostrar todos os resultados da calibração
	@echo "📊 Resultados da Calibração"
	@echo "═══════════════════════════════════════════════════════════"
	@if [ -f $(CALIBRATION_DIR)/trsd_optuna_best_params.json ]; then \
		echo "🎯 Melhores Parâmetros:"; \
		cat $(CALIBRATION_DIR)/trsd_optuna_best_params.json | jq . 2>/dev/null || cat $(CALIBRATION_DIR)/trsd_optuna_best_params.json; \
		echo ""; \
	fi
	@if [ -f $(CALIBRATION_DIR)/optuna_incremental_results.json ]; then \
		echo "📈 Progresso Incremental:"; \
		cat $(CALIBRATION_DIR)/optuna_incremental_results.json | jq '.best_trial' 2>/dev/null || echo "Arquivo não é JSON válido"; \
		echo ""; \
	fi
	@if [ -f $(CALIBRATION_DIR)/trsd_optuna_report.md ]; then \
		echo "📄 Relatório disponível em: $(CALIBRATION_DIR)/trsd_optuna_report.md"; \
	fi
	@echo "═══════════════════════════════════════════════════════════"

# ============================================================================
# DOCKER & DEPLOYMENT
# ============================================================================

network: ## Criar rede Docker ytcaption-network (se não existir)
	@docker network inspect ytcaption-network >/dev/null 2>&1 || \
		(docker network create ytcaption-network && echo "✅ Rede ytcaption-network criada") || \
		echo "✅ Rede ytcaption-network já existe"

build: network ## Build da imagem Docker
	@echo "🔨 Construindo imagem Docker..."
	$(DOCKER_COMPOSE) build

up: network ## Iniciar serviços em background
	@echo "🚀 Iniciando serviços..."
	$(DOCKER_COMPOSE) up -d
	@echo "✅ Serviços iniciados"
	@echo "📊 Status: make status"
	@echo "📋 Logs: make logs"

down: ## Parar e remover containers
	@echo "🛑 Parando serviços..."
	$(DOCKER_COMPOSE) down

restart: ## Reiniciar serviços
	@echo "🔄 Reiniciando serviços..."
	$(DOCKER_COMPOSE) restart
	@echo "✅ Serviços reiniciados"

status: ## Mostrar status dos containers
	@echo "📊 Status dos Containers"
	@echo "═══════════════════════════════════════════════════════════"
	$(DOCKER_COMPOSE) ps
	@echo ""
	@echo "Calibração:"
	@CALCONTAINER=$$(docker ps --format "{{.Names}}" | grep -E "calibrate|optuna|make-video-run" | head -1); \
	if [ -n "$$CALCONTAINER" ]; then \
		echo "  ✅ ATIVA: $$CALCONTAINER"; \
		echo "  Ver detalhes: make cal-status"; \
	else \
		echo "  ❌ Não rodando"; \
	fi
	@echo "═══════════════════════════════════════════════════════════"

ps: status ## Alias para 'make status'

# ============================================================================
# COMPATIBILIZAÇÃO DE VÍDEOS
# ============================================================================

compatibility: ## Executar compatibilização de vídeos em um diretório
	@if [ -z "$(DIR)" ]; then \
		echo "❌ Use: make compatibility DIR=/caminho/para/videos"; \
		echo ""; \
		echo "Exemplo:"; \
		echo "  make compatibility DIR=data/raw/videos/job123"; \
		echo ""; \
		echo "O que faz:"; \
		echo "  • Detecta specs de todos os vídeos .mp4"; \
		echo "  • Define vídeo-alvo baseado no primeiro"; \
		echo "  • Converte vídeos incompatíveis automaticamente"; \
		echo "  • Mantém vídeos originais como backup"; \
		exit 1; \
	fi
	@$(VENV_PYTHON) scripts/compatibility_fixer.py "$(DIR)"

compatibility-check: ## Verificar se vídeos em diretório são compatíveis (sem converter)
	@if [ -z "$(DIR)" ]; then \
		echo "❌ Use: make compatibility-check DIR=/caminho/para/videos"; \
		exit 1; \
	fi
	@$(VENV_PYTHON) scripts/compatibility_checker.py "$(DIR)"

# ============================================================================
# MANUTENÇÃO & LIMPEZA
# ============================================================================

clean: ## Limpar arquivos temporários e cache
	@echo "🧹 Limpando arquivos temporários..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ 2>/dev/null || true
	@echo "✅ Limpeza concluída"

clean-storage: ## Limpar storage (⚠️ CUIDADO: remove vídeos)
	@echo "⚠️  ATENÇÃO: Isso removerá arquivos temporários do pipeline data/!"
	@echo "✅ PRESERVADO: data/approved/videos/ e data/raw/shorts/blacklist.db"
	@read -p "Continuar? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo "🧹 Limpando data/raw/audio/..."; \
		rm -rf $(RAW_DIR)/audio/* 2>/dev/null || true; \
		echo "🧹 Limpando data/transform/..."; \
		rm -rf $(TRANSFORM_DIR)/videos/* 2>/dev/null || true; \
		rm -rf $(TRANSFORM_DIR)/temp/* 2>/dev/null || true; \
		echo "🧹 Limpando data/validate/..."; \
		rm -rf $(VALIDATE_DIR)/in_progress/* 2>/dev/null || true; \
		rm -rf $(VALIDATE_DIR)/test_datasets/* 2>/dev/null || true; \
		echo "✅ data/ limpo (approved/videos e blacklist.db preservados)"; \
	fi

storage-info: ## Mostrar informações sobre o storage
	@echo "📊 Data Pipeline Information"
	@echo "═══════════════════════════════════════════════════════════"
	@echo "📂 Estrutura:"
	@find $(DATA_DIR) -maxdepth 2 -type d | sort
	@echo ""
	@echo "💾 Tamanho por pasta:"
	@du -sh $(DATA_DIR)/* 2>/dev/null | sort -h
	@echo ""
	@echo "📹 Contagem de arquivos:"
	@echo "  raw/shorts: $$(find $(RAW_DIR)/shorts -name "*.mp4" -o -name "*.webm" 2>/dev/null | wc -l) arquivos"
	@echo "  transform/videos: $$(find $(TRANSFORM_DIR)/videos -name "*.mp4" 2>/dev/null | wc -l) vídeos"
	@echo "  approved/videos: $$(find $(APPROVED_DIR)/videos -name "*.mp4" 2>/dev/null | wc -l) vídeos"
	@echo "═══════════════════════════════════════════════════════════"

clean-all: clean ## Limpeza total (cache + containers + volumes)
	@echo "🧹 Limpeza TOTAL..."
	$(DOCKER_COMPOSE) down -v --remove-orphans
	docker system prune -f
	@echo "✅ Limpeza total concluída"

validate: ## Validar configuração e estrutura
	@echo "🔍 Validando configuração..."
	@echo ""
	@echo "📂 Estrutura de diretórios:"
	@test -d $(DATA_DIR) && echo "  ✅ data/" || echo "  ❌ data/ (criando...)" && mkdir -p $(DATA_DIR)
	@test -d $(RAW_DIR)/shorts && echo "  ✅ data/raw/shorts/" || echo "  ❌ data/raw/shorts/ (criando...)" && mkdir -p $(RAW_DIR)/shorts
	@test -d $(TRANSFORM_DIR)/videos && echo "  ✅ data/transform/videos/" || echo "  ❌ data/transform/videos/ (criando...)" && mkdir -p $(TRANSFORM_DIR)/videos
	@test -d $(VALIDATE_DIR)/in_progress && echo "  ✅ data/validate/in_progress/" || echo "  ❌ data/validate/in_progress/ (criando...)" && mkdir -p $(VALIDATE_DIR)/in_progress
	@test -d $(APPROVED_DIR)/videos && echo "  ✅ data/approved/videos/" || echo "  ❌ data/approved/videos/ (criando...)" && mkdir -p $(APPROVED_DIR)/videos
	@test -d $(CALIBRATION_DIR) && echo "  ✅ data/calibration/" || echo "  ❌ data/calibration/ (criando...)" && mkdir -p $(CALIBRATION_DIR)
	@echo ""
	@echo "📄 Arquivos de configuração:"
	@test -f .env && echo "  ✅ .env" || echo "  ⚠️  .env não encontrado"
	@test -f docker/docker-compose.yml && echo "  ✅ docker-compose.yml" || echo "  ❌ docker-compose.yml"
	@test -f requirements.txt && echo "  ✅ requirements.txt" || echo "  ❌ requirements.txt"
	@echo ""
	@echo "🐍 Scripts Python:"
	@test -f calibrate_trsd_optuna.py && echo "  ✅ calibrate_trsd_optuna.py" || echo "  ⚠️  calibrate_trsd_optuna.py"
	@test -f run.py && echo "  ✅ run.py" || echo "  ❌ run.py"
	@echo ""
	@echo "✅ Validação concluída"

# ============================================================================
# MONITORAMENTO
# ============================================================================

health: ## Verificar health do serviço
	@echo "🏥 Health Check"
	@echo "═══════════════════════════════════════════════════════════"
	@curl -s $(API_BASE_URL)/health 2>/dev/null | jq . || echo "❌ Serviço não responde ($(API_BASE_URL))"
	@echo "═══════════════════════════════════════════════════════════"

metrics: ## Mostrar métricas do sistema
	@echo "📊 Métricas do Sistema"
	@echo "═══════════════════════════════════════════════════════════"
	@echo "💾 Uso de Disco (data/):"
	@du -sh $(DATA_DIR)/* 2>/dev/null | sort -h || echo "  (vazio)"
	@echo ""
	@echo "🐳 Recursos Docker:"
	@docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep make-video || echo "  Serviço não está rodando"
	@echo "═══════════════════════════════════════════════════════════"

# ============================================================================
# API CONTROLE
# ============================================================================

api-root: ## GET / (informações do serviço)
	@curl -s $(API_BASE_URL)/ | jq .

api-openapi: ## GET /openapi.json (contrato completo da API)
	@curl -s $(API_BASE_URL)/openapi.json | jq '.info, .paths | keys'

api-health: ## GET /health
	@curl -s $(API_BASE_URL)/health | jq .

api-metrics: ## GET /metrics
	@curl -s $(API_BASE_URL)/metrics | head -40

api-download: ## POST /download (query=$(API_QUERY), max_shorts=$(API_MAX_SHORTS))
	@curl -s -X POST "$(API_BASE_URL)/download" \
		-F "query=$(API_QUERY)" \
		-F "max_shorts=$(API_MAX_SHORTS)" | jq .

api-make-video: ## POST /make-video (requer AUDIO_FILE=/caminho/audio.mp3)
	@if [ -z "$(AUDIO_FILE)" ]; then echo "❌ Use: make api-make-video AUDIO_FILE=/path/audio.mp3"; exit 1; fi
	@curl -s -X POST "$(API_BASE_URL)/make-video" \
		-F "audio_file=@$(AUDIO_FILE)" \
		-F "query=$(API_QUERY)" \
		-F "max_shorts=$(API_MAX_SHORTS)" | jq .

api-jobs: ## GET /jobs (limit=$(API_LIMIT), status=$(API_STATUS))
	@if [ -n "$(API_STATUS)" ]; then \
		curl -s "$(API_BASE_URL)/jobs?limit=$(API_LIMIT)&status=$(API_STATUS)" | jq .; \
	else \
		curl -s "$(API_BASE_URL)/jobs?limit=$(API_LIMIT)" | jq .; \
	fi

api-job: ## GET /jobs/{job_id} (requer JOB_ID=...)
	@if [ -z "$(JOB_ID)" ]; then echo "❌ Use: make api-job JOB_ID=<job_id>"; exit 1; fi
	@curl -s "$(API_BASE_URL)/jobs/$(JOB_ID)" | jq .

api-job-delete: ## DELETE /jobs/{job_id} (requer JOB_ID=...)
	@if [ -z "$(JOB_ID)" ]; then echo "❌ Use: make api-job-delete JOB_ID=<job_id>"; exit 1; fi
	@curl -s -X DELETE "$(API_BASE_URL)/jobs/$(JOB_ID)" | jq .

api-download-file: ## GET /download/{job_id} (requer JOB_ID=...)
	@if [ -z "$(JOB_ID)" ]; then echo "❌ Use: make api-download-file JOB_ID=<job_id>"; exit 1; fi
	@mkdir -p /tmp/make-video-downloads
	@curl -s -L "$(API_BASE_URL)/download/$(JOB_ID)" -o "/tmp/make-video-downloads/video_$(JOB_ID).mp4" && \
		echo "✅ Salvo em /tmp/make-video-downloads/video_$(JOB_ID).mp4"

api-cache-stats: ## GET /cache/stats
	@curl -s "$(API_BASE_URL)/cache/stats" | jq .

api-cache-cleanup: ## POST /cache/cleanup?days=$(DAYS)
	@curl -s -X POST "$(API_BASE_URL)/cache/cleanup?days=$(DAYS)" | jq .

api-admin-stats: ## GET /admin/stats
	@curl -s "$(API_BASE_URL)/admin/stats" | jq .

api-admin-queue: ## GET /admin/queue
	@curl -s "$(API_BASE_URL)/admin/queue" | jq .

api-admin-cleanup: ## POST /admin/cleanup (deep=$(DEEP), purge=$(PURGE_CELERY_QUEUE))
	@curl -s -X POST "$(API_BASE_URL)/admin/cleanup?deep=$(DEEP)&purge_celery_queue=$(PURGE_CELERY_QUEUE)" | jq .

api-cleanup-failed: ## POST /jobs/cleanup-failed
	@curl -s -X POST "$(API_BASE_URL)/jobs/cleanup-failed" | jq .

api-orphans: ## GET /jobs/orphaned?max_age_minutes=$(MAX_AGE_MINUTES)
	@curl -s "$(API_BASE_URL)/jobs/orphaned?max_age_minutes=$(MAX_AGE_MINUTES)" | jq .

api-orphans-cleanup: ## POST /jobs/orphaned/cleanup
	@curl -s -X POST "$(API_BASE_URL)/jobs/orphaned/cleanup?max_age_minutes=$(MAX_AGE_MINUTES)&mark_as_failed=$(MARK_AS_FAILED)" | jq .

api-admin-cleanup-orphans: ## POST /admin/cleanup-orphans?max_age_minutes=$(MAX_AGE_MINUTES)
	@curl -s -X POST "$(API_BASE_URL)/admin/cleanup-orphans?max_age_minutes=$(MAX_AGE_MINUTES)" | jq .

api-smoke: ## Executa verificação rápida de endpoints de controle
	@echo "🔎 API Smoke ($(API_BASE_URL))"
	@curl -s $(API_BASE_URL)/health | jq -r '.status'
	@curl -s $(API_BASE_URL)/admin/stats | jq -r '.jobs.total'
	@curl -s $(API_BASE_URL)/cache/stats | jq . >/dev/null && echo "cache: ok"

# ============================================================================
# UTILITÁRIOS
# ============================================================================

env-check: ## Verificar variáveis de ambiente
	@echo "🔐 Variáveis de Ambiente"
	@echo "═══════════════════════════════════════════════════════════"
	@grep -E "^[A-Z_]+" .env 2>/dev/null | sed 's/=.*/=***/' || echo "❌ .env não encontrado"
	@echo "═══════════════════════════════════════════════════════════"

config: ## Mostrar configuração atual
	@echo "⚙️  Configuração Atual"
	@echo "═══════════════════════════════════════════════════════════"
	@echo "Serviço: $(DOCKER_SERVICE)"
	@echo "Data: $(DATA_DIR)"
	@echo "API: $(API_BASE_URL)"
	@echo "Calibração: $(CALIBRATION_DIR)"
	@echo "Trials (calibração): $(OPTUNA_TRIALS)"
	@echo "Timeout (calibração): $(OPTUNA_TIMEOUT)s"
	@echo "═══════════════════════════════════════════════════════════"

version: ## Mostrar versão e informações
	@echo "ℹ️  Make-Video Service"
	@echo "═══════════════════════════════════════════════════════════"
	@echo "Versão: 2.1"
	@echo "Python: $$($(PYTHON) --version)"
	@echo "Docker: $$(docker --version)"
	@echo "Docker Compose: $$(docker compose version)"
	@echo "═══════════════════════════════════════════════════════════"

# ============================================================================
# ATALHOS RÁPIDOS
# ============================================================================

quick: test-quick ## Alias para 'make test-quick'

cal: calibrate ## Alias para 'make calibrate'

cal-start: calibrate-start ## Alias para 'make calibrate-start'

cal-status: calibrate-status ## Alias para 'make calibrate-status'

cal-logs: calibrate-logs ## Alias para 'make calibrate-logs'

cal-watch: calibrate-watch ## Alias para 'make calibrate-watch'

cal-stop: calibrate-stop ## Alias para 'make calibrate-stop'

cal-apply: calibrate-apply ## Alias para 'make calibrate-apply'

# ============================================================================
# DEVELOPMENT WORKFLOWS
# ============================================================================

dev-setup: install validate ## Setup completo para desenvolvimento
	@echo "✅ Setup de desenvolvimento concluído"
	@echo ""
	@echo "Próximos passos:"
	@echo "  1. Configurar .env: cp .env.example .env"
	@echo "  2. Iniciar serviços: make up"
	@echo "  3. Ver logs: make logs"

prod-deploy: build up ## Deploy em produção (build + up)
	@echo "✅ Deploy concluído"
	@echo "📊 Status: make status"

full-test: test-imports test-validate test-coverage ## Executar bateria completa de testes
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "🎉 BATERIA COMPLETA DE TESTES CONCLUÍDA!"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ============================================================================
# TARGETS ADICIONAIS (logs de containers, shells, celery/beat, rebuild)
# ============================================================================

build-nc: network ## Build da imagem Docker sem cache
	@echo "🔨 Building make-video (no cache)..."
	$(DOCKER_COMPOSE) build --no-cache

rebuild: build-nc up ## Rebuild completo sem cache + iniciar

logs-api: ## Ver logs do container da API
	@docker logs -f ytcaption-make-video

logs-celery: ## Ver logs do container Celery
	@docker logs -f ytcaption-make-video-celery

logs-beat: ## Ver logs do container Celery Beat
	@docker logs -f ytcaption-make-video-celery-beat

celery-restart: ## Reiniciar Celery worker
	@echo "🔄 Reiniciando Celery worker..."
	@docker restart ytcaption-make-video-celery
	@echo "✅ Celery reiniciado!"

beat-restart: ## Reiniciar Celery Beat
	@echo "🔄 Reiniciando Celery Beat..."
	@docker restart ytcaption-make-video-celery-beat
	@echo "✅ Beat reiniciado!"

purge: ## Limpar fila do Celery
	@echo "🧹 Limpando fila do Celery..."
	@docker exec ytcaption-make-video-celery python -m celery -A app.infrastructure.celery_config purge -f 2>/dev/null || \
		echo "⚠️  Nao foi possivel limpar fila"

shell-api: ## Shell no container da API
	@docker exec -it ytcaption-make-video /bin/bash

shell-celery: ## Shell no container do Celery
	@docker exec -it ytcaption-make-video-celery /bin/bash

shell-beat: ## Shell no container do Beat
	@docker exec -it ytcaption-make-video-celery-beat /bin/bash

clean-docker: ## Limpar imagens Docker
	@echo "🧹 Limpando imagens Docker..."
	-docker rmi -f ytcaption-make-video ytcaption-make-video-celery ytcaption-make-video-celery-beat 2>/dev/null
	@echo "✅ Imagens removidas!"

fix-permissions: ## Corrigir permissoes dos diretorios data/
	@echo "🔧 Corrigindo permissoes..."
	@mkdir -p $(DATA_DIR)/logs $(DATA_DIR)/raw $(DATA_DIR)/transform $(DATA_DIR)/validate $(DATA_DIR)/approved $(DATA_DIR)/calibration
	-sudo chown -R 1000:1000 $(DATA_DIR) 2>/dev/null
	chmod -R 777 $(DATA_DIR)
	@echo "✅ Permissoes corrigidas!"
