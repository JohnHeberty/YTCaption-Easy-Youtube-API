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

DOCKER_COMPOSE := docker compose
DOCKER_SERVICE := make-video
PYTHON := python3
DATA_DIR := ./data
RAW_DIR := $(DATA_DIR)/raw
TRANSFORM_DIR := $(DATA_DIR)/transform
VALIDATE_DIR := $(DATA_DIR)/validate
APPROVED_DIR := $(DATA_DIR)/approved
CALIBRATION_DIR := $(DATA_DIR)/calibration
LOG_DIR := /tmp
API_BASE_URL := http://localhost:8004
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
	@echo "  • Desenvolvimento: install, dev, logs, shell"
	@echo "  • Testes: test, test-quick, test-imports"
	@echo "  • API Controle: api-health, api-download, api-jobs, api-admin-stats"
	@echo "  • Calibração: calibrate-start, calibrate-status, calibrate-watch, calibrate-logs"
	@echo "  • Deployment: build, up, down, restart"
	@echo "  • Manutenção: clean, clean-all, validate"
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

install: ## Instalar dependências Python localmente
	@echo "📦 Instalando dependências..."
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	@echo "✅ Dependências instaladas"

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

test: ## Executar todos os testes
	@echo "🧪 Executando testes completos..."
	$(PYTHON) -m pytest tests/ -v --tb=short

test-quick: ## Executar testes rápidos (sem calibração)
	@echo "⚡ Executando testes rápidos..."
	$(PYTHON) -m pytest tests/ -v -k "not calibration" --tb=short

test-imports: ## Validar todos os imports
	@echo "🔍 Validando imports..."
	@$(PYTHON) -c "from app.video_processing.video_validator import VideoValidator; print('✅ VideoValidator')"
	@$(PYTHON) -c "from app.video_processing.ocr_detector import get_ocr_detector; print('✅ get_ocr_detector')"
	@$(PYTHON) -c "from app.infrastructure.celery_tasks import recover_orphaned_jobs; print('✅ celery_tasks')"
	@echo "✅ Todos os imports funcionando"

test-coverage: ## Executar testes com cobertura
	@echo "📊 Executando testes com cobertura..."
	$(PYTHON) -m pytest tests/ --cov=app --cov-report=html --cov-report=term

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

build: ## Build da imagem Docker
	@echo "🔨 Construindo imagem Docker..."
	$(DOCKER_COMPOSE) build

up: ## Iniciar serviços em background
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
	@test -f docker-compose.yml && echo "  ✅ docker-compose.yml" || echo "  ❌ docker-compose.yml"
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

full-test: test-imports test ## Executar bateria completa de testes
	@echo "✅ Todos os testes concluídos"
