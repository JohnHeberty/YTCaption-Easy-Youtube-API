# ============================================================================
# Makefile - Audio-Transcriber Service (se4)
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
DOCKER_SERVICE := audio-transcriber-service
SERVICE_NAME := audio-transcriber
SERVICE_TITLE := Audio-Transcriber
PYTHON := python3
VENV := .venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PYTEST := $(VENV_BIN)/pytest
LOG_DIR := ./data/logs
MODELS_DIR := ./data/models
UPLOADS_DIR := ./data/uploads
TRANSCRIPTIONS_DIR := ./data/transcriptions
TEMP_DIR := ./data/temp
API_BASE_URL := http://localhost:8004
PORT ?= 8004
TEST_AUDIO := tests/TEST5.ogg

# Configuracoes do Whisper
WHISPER_MODEL ?= small
WHISPER_DEVICE ?= cpu

# Nomes dos containers
CONTAINER_API := audio-transcriber-api
CONTAINER_CELERY := audio-transcriber-celery
CONTAINER_BEAT := audio-transcriber-beat

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
	@echo "Categorias:"
	@echo "  • Desenvolvimento: venv, install, dev, shell"
	@echo "  • Modelos: model-download, model-test, model-info"
	@echo "  • Testes: test, test-unit, test-integration, test-coverage"
	@echo "  • Docker: build, build-nc, up, down, restart, logs, ps, rebuild"
	@echo "  • API: api-health, api-transcribe, api-jobs, api-languages, api-models"
	@echo "  • Celery: celery-logs, celery-restart"
	@echo "  • Beat: beat-logs, beat-restart"
	@echo "  • Producao: prod-build, prod-up, prod-logs, prod-status"
	@echo "  • Manutencao: clean, clean-all, clean-models, validate"
	@echo "  • Utilitarios: shell-api, shell-celery, shell-beat, diagnose, info"
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
	@echo "   Device: $(WHISPER_DEVICE)"
	@echo "   Model: $(WHISPER_MODEL)"
	@echo "   Port: $(PORT)"
	WHISPER_DEVICE=$(WHISPER_DEVICE) WHISPER_MODEL=$(WHISPER_MODEL) $(VENV_PYTHON) run.py

shell: ## Abrir shell Python com ambiente configurado
	@echo "Abrindo Python shell..."
	$(VENV_PYTHON)

# ============================================================================
# MODELOS
# ============================================================================

model-download: venv ## Baixar modelo Whisper localmente (use MODEL=tiny|base|small|medium|large)
	@echo "Baixando modelo Whisper: $(WHISPER_MODEL)..."
	@mkdir -p $(MODELS_DIR)
	$(VENV_PYTHON) -c "from faster_whisper import WhisperModel; WhisperModel('$(WHISPER_MODEL)', device='cpu', compute_type='int8', download_root='$(MODELS_DIR)')"
	@echo "  Modelo $(WHISPER_MODEL) baixado em $(MODELS_DIR)"

model-test: venv ## Testar modelo Whisper com audio de teste
	@echo "Testando modelo Whisper..."
	@if [ -f "$(TEST_AUDIO)" ]; then \
		$(VENV_PYTHON) test-prod/test_with_audio.py; \
	else \
		echo "  Audio de teste nao encontrado: $(TEST_AUDIO)"; \
		$(VENV_PYTHON) test-prod/test_minimal.py; \
	fi

model-info: ## Mostrar informacoes dos modelos disponiveis
	@echo "Modelos Faster-Whisper Disponiveis:"
	@echo ""
	@echo "  Modelo    VRAM    Velocidade    Qualidade"
	@echo "  --------  ------  ------------  ---------"
	@echo "  tiny      ~1 GB   ~32x          **"
	@echo "  base      ~1 GB   ~16x          ***"
	@echo "  small     ~2 GB   ~6x           ****"
	@echo "  medium    ~5 GB   ~2x           *****"
	@echo "  large     ~10GB   ~1x           ******"
	@echo ""
	@echo "  Modelo atual: $(WHISPER_MODEL)"
	@echo "  Device: $(WHISPER_DEVICE)"
	@echo ""
	@if [ -d "$(MODELS_DIR)" ]; then \
		echo "  Modelos baixados:"; \
		ls -lh $(MODELS_DIR) 2>/dev/null || echo "   (vazio)"; \
	else \
		echo "  Diretorio de modelos nao encontrado"; \
	fi

# ============================================================================
# TESTES
# ============================================================================

test: ## Rodar todos os testes
	$(VENV_PYTEST) tests/ -v --tb=short

test-unit: venv ## Rodar testes unitarios
	@echo "Rodando testes unitarios..."
	$(VENV_PYTEST) tests/ -v --tb=short -m unit 2>/dev/null || $(VENV_PYTEST) tests/unit/ -v --tb=short

test-integration: venv ## Rodar testes de integracao
	@echo "Rodando testes de integracao..."
	$(VENV_PYTEST) tests/ -v --tb=short -m integration 2>/dev/null || $(VENV_PYTEST) tests/integration/ -v --tb=short

test-coverage: venv ## Rodar testes com cobertura
	@echo "Rodando testes com coverage..."
	$(VENV_PYTEST) tests/ --cov=app --cov-report=html --cov-report=term
	@echo "  Relatorio HTML: htmlcov/index.html"

# ============================================================================
# DOCKER
# ============================================================================

network: ## Criar rede Docker compartilhada
	@echo "Criando rede Docker..."
	@docker network create ytcaption_network 2>/dev/null || echo "  Rede ja existe"

build: ## Build das imagens Docker
	@echo "Building $(SERVICE_TITLE)..."
	$(DOCKER_COMPOSE) build

build-nc: ## Build das imagens Docker sem cache
	@echo "Building $(SERVICE_TITLE) (no cache)..."
	$(DOCKER_COMPOSE) build --no-cache

up: network ## Subir servico em background
	@echo "Iniciando $(SERVICE_TITLE)..."
	$(DOCKER_COMPOSE) up -d
	@echo ""
	@echo "  Servico iniciado!"
	@echo "  API: $(API_BASE_URL)"
	@echo "  Logs: make logs"
	@echo "  Health: make api-health"

down: ## Parar e remover containers
	@echo "Parando $(SERVICE_TITLE)..."
	$(DOCKER_COMPOSE) down

restart: down up ## Reiniciar servico

rebuild: build-nc up ## Rebuild completo sem cache + iniciar

logs: ## Mostrar logs do servico (API + Celery + Beat)
	$(DOCKER_COMPOSE) logs -f --tail=100

logs-api: ## Mostrar logs da API
	@docker logs -f --tail=100 $(CONTAINER_API)

logs-celery: ## Mostrar logs do Celery worker
	@docker logs -f --tail=100 $(CONTAINER_CELERY)

logs-beat: ## Mostrar logs do Celery beat
	@docker logs -f --tail=100 $(CONTAINER_BEAT)

ps: ## Mostrar status dos containers
	@$(DOCKER_COMPOSE) ps

# ============================================================================
# API
# ============================================================================

api-health: ## Verificar saude da API
	@echo "Verificando saude da API..."
	@curl -s $(API_BASE_URL)/health | python3 -m json.tool || echo "  API nao esta respondendo"

api-languages: ## Listar idiomas suportados
	@echo "Idiomas suportados:"
	@curl -s $(API_BASE_URL)/languages | python3 -m json.tool

api-models: ## Listar modelos disponiveis
	@echo "Modelos disponiveis:"
	@curl -s $(API_BASE_URL)/models | python3 -m json.tool

api-jobs: ## Listar jobs recentes
	@echo "Jobs recentes:"
	@curl -s $(API_BASE_URL)/jobs | python3 -m json.tool

api-job: ## Mostrar detalhes de um job (use JOB_ID=...)
	@curl -s $(API_BASE_URL)/jobs/$(JOB_ID) | python3 -m json.tool

api-transcribe: ## Transcrever audio de teste (use FILE=caminho)
	@echo "Transcrevendo audio..."
	@FILE=$${FILE:-$(TEST_AUDIO)}; \
	if [ -f "$$FILE" ]; then \
		curl -X POST $(API_BASE_URL)/transcribe \
			-F "audio_file=@$$FILE" \
			-F "language=pt" | python3 -m json.tool; \
	else \
		echo "  Audio nao encontrado: $$FILE"; \
	fi

api-delete-job: ## Deletar um job (use JOB_ID=...)
	@curl -X DELETE $(API_BASE_URL)/jobs/$(JOB_ID)

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
	@docker exec $(CONTAINER_CELERY) python -m celery -A app.celery_config purge -f 2>/dev/null || \
		echo "  Nao foi possivel limpar fila"

# ============================================================================
# PRODUCAO
# ============================================================================

prod-build: ## Build otimizado para producao
	@echo "Building para producao..."
	DOCKER_BUILDKIT=1 $(DOCKER_COMPOSE) build --build-arg BUILD_ENV=production

prod-up: network prod-build ## Deploy em producao
	@echo "Deploying em producao..."
	$(DOCKER_COMPOSE) up -d
	@echo ""
	@echo "  Producao iniciada!"
	@make api-health

prod-logs: ## Logs de producao (ultimas 500 linhas)
	$(DOCKER_COMPOSE) logs --tail=500

prod-status: ## Status de producao
	@echo "Status de Producao:"
	@echo ""
	@make ps
	@echo ""
	@make api-health

# ============================================================================
# MANUTENCAO
# ============================================================================

clean: ## Limpar arquivos temporarios e cache
	@echo "Limpando arquivos temporarios..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "  Cache limpo!"

clean-uploads: ## Limpar arquivos de upload
	@echo "Limpando uploads..."
	@if [ -d "$(UPLOADS_DIR)" ]; then \
		rm -rf $(UPLOADS_DIR)/*; \
		echo "  Uploads limpos!"; \
	else \
		echo "  Diretorio de uploads nao encontrado"; \
	fi

clean-transcriptions: ## Limpar transcricoes antigas (>7 dias)
	@echo "Limpando transcricoes..."
	@if [ -d "$(TRANSCRIPTIONS_DIR)" ]; then \
		find $(TRANSCRIPTIONS_DIR) -type f -mtime +7 -delete; \
		echo "  Transcricoes antigas removidas (>7 dias)"; \
	else \
		echo "  Diretorio de transcricoes nao encontrado"; \
	fi

clean-models: ## Remover modelos baixados (CUIDADO!)
	@echo "ATENCAO: Isso removera todos os modelos baixados!"
	@read -p "Continuar? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf $(MODELS_DIR)/*; \
		echo "  Modelos removidos!"; \
	else \
		echo "  Operacao cancelada"; \
	fi

clean-all: clean clean-uploads clean-transcriptions ## Limpar tudo (exceto modelos)
	@echo "Limpando Docker..."
	$(DOCKER_COMPOSE) down -v 2>/dev/null || true
	@echo "  Limpeza completa!"

clean-docker: ## Limpar imagens Docker
	@echo "Limpando imagens Docker..."
	-docker rmi -f $(CONTAINER_API) $(CONTAINER_CELERY) $(CONTAINER_BEAT) 2>/dev/null
	@echo "  Imagens removidas!"

validate: ## Validar configuracoes e diretorios
	@echo "Validando configuracoes..."
	@echo ""
	@echo "  Diretorios:"
	@mkdir -p $(LOG_DIR) $(MODELS_DIR) $(UPLOADS_DIR) $(TRANSCRIPTIONS_DIR) $(TEMP_DIR)
	@ls -ld $(LOG_DIR) $(MODELS_DIR) $(UPLOADS_DIR) $(TRANSCRIPTIONS_DIR) $(TEMP_DIR) 2>/dev/null
	@echo ""
	@echo "  docker-compose.yml:"
	@$(DOCKER_COMPOSE) config > /dev/null 2>&1 && echo "    valido" || echo "    invalido"
	@echo ""
	@echo "  Python:"
	@$(VENV_PYTHON) --version 2>/dev/null || echo "    venv nao criado (make venv)"
	@echo ""
	@echo "  Faster-Whisper:"
	@$(VENV_PYTHON) -c "import faster_whisper; print(f'    Versao: {faster_whisper.__version__}')" 2>/dev/null || echo "    Nao instalado"
	@echo ""
	@echo "  Docker:"
	@docker --version
	@$(DOCKER_COMPOSE) --version

# ============================================================================
# DIAGNOSTICO
# ============================================================================

diagnose: ## Diagnostico completo do sistema
	@echo "Diagnostico do $(SERVICE_TITLE)..."
	@echo ""
	@echo "========================================"
	@echo "1. AMBIENTE"
	@echo "========================================"
	@make validate
	@echo ""
	@echo "========================================"
	@echo "2. DOCKER"
	@echo "========================================"
	@make ps
	@echo ""
	@echo "========================================"
	@echo "3. API"
	@echo "========================================"
	@make api-health
	@echo ""
	@echo "========================================"
	@echo "4. MODELOS"
	@echo "========================================"
	@make model-info
	@echo ""
	@echo "  Diagnostico completo!"

info: ## Informacoes do servico
	@echo ""
	@echo "$(SERVICE_TITLE) Service (se4)"
	@echo "  Porta: $(PORT)"
	@echo "  API:   $(API_BASE_URL)"
	@echo "  Docs:  $(API_BASE_URL)/docs"
	@echo "  Modelo: $(WHISPER_MODEL)"
	@echo "  Device: $(WHISPER_DEVICE)"
	@echo "  Diretorio: $(PWD)"
	@echo ""
	@echo "  Containers:"
	@echo "    API:    $(CONTAINER_API)"
	@echo "    Celery: $(CONTAINER_CELERY)"
	@echo "    Beat:   $(CONTAINER_BEAT)"
	@echo ""
	@echo "  Diretorios:"
	@echo "    Modelos:       $(MODELS_DIR)"
	@echo "    Uploads:       $(UPLOADS_DIR)"
	@echo "    Transcricoes:  $(TRANSCRIPTIONS_DIR)"
	@echo "    Logs:          $(LOG_DIR)"
	@echo ""
	@echo "  Endpoints:"
	@echo "    Health:      $(API_BASE_URL)/health"
	@echo "    Transcribe:  $(API_BASE_URL)/transcribe"
	@echo "    Jobs:        $(API_BASE_URL)/jobs"
	@echo "    Languages:   $(API_BASE_URL)/languages"
	@echo "    Models:      $(API_BASE_URL)/models"

# ============================================================================
# UTILITARIOS
# ============================================================================

shell-api: ## Executar bash no container da API
	@docker exec -it $(CONTAINER_API) /bin/bash

shell-celery: ## Executar bash no container do Celery
	@docker exec -it $(CONTAINER_CELERY) /bin/bash

shell-beat: ## Executar bash no container do Beat
	@docker exec -it $(CONTAINER_BEAT) /bin/bash

fix-permissions: ## Corrigir permissoes dos diretorios
	@echo "Corrigindo permissoes..."
	@mkdir -p $(LOG_DIR) $(MODELS_DIR) $(UPLOADS_DIR) $(TRANSCRIPTIONS_DIR) $(TEMP_DIR)
	-sudo chown -R 1000:1000 $(LOG_DIR) $(MODELS_DIR) $(UPLOADS_DIR) $(TRANSCRIPTIONS_DIR) $(TEMP_DIR) 2>/dev/null
	chmod -R 777 $(LOG_DIR) $(MODELS_DIR) $(UPLOADS_DIR) $(TRANSCRIPTIONS_DIR) $(TEMP_DIR)
	@echo "  Permissoes corrigidas para uid 1000!"
