# ============================================================================
# Makefile - Audio-Transcriber Service
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
DOCKER_SERVICE := audio-transcriber-celery
PYTHON := python3
VENV := .venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PYTEST := $(VENV_BIN)/pytest
LOG_DIR := ./logs
MODELS_DIR := ./models
UPLOADS_DIR := ./uploads
TRANSCRIPTIONS_DIR := ./transcriptions
TEMP_DIR := ./temp
API_BASE_URL := http://localhost:8003
TEST_AUDIO := tests/TEST-.ogg

# Configurações
WHISPER_MODEL ?= base
WHISPER_DEVICE ?= cpu
PORT ?= 8003

# ============================================================================
# HELP
# ============================================================================

help: ## Mostrar esta mensagem de ajuda
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║      Audio-Transcriber Service - Comandos Disponíveis          ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "📚 Categorias:"
	@echo "  • Desenvolvimento: install, venv, dev, logs, shell"
	@echo "  • Testes: test, test-unit, test-integration, test-prod"
	@echo "  • Modelos: model-download, model-test, model-info"
	@echo "  • API: api-health, api-transcribe, api-jobs, api-languages"
	@echo "  • Deployment: network, build, up, down, restart"
	@echo "  • Manutenção: clean, clean-all, clean-models, validate"
	@echo ""
	@echo "🎯 Fluxo de Desenvolvimento:"
	@echo "  1. make install         → Instalar dependências"
	@echo "  2. make model-download  → Baixar modelo Whisper"
	@echo "  3. make test-prod       → Testar localmente"
	@echo "  4. make build           → Build containers"
	@echo "  5. make up              → Subir serviço"
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
	@echo "🚀 Iniciando audio-transcriber em modo dev..."
	@echo "   Device: $(WHISPER_DEVICE)"
	@echo "   Model: $(WHISPER_MODEL)"
	@echo "   Port: $(PORT)"
	WHISPER_DEVICE=$(WHISPER_DEVICE) WHISPER_MODEL=$(WHISPER_MODEL) $(VENV_PYTHON) run.py

shell: ## Abrir shell Python com ambiente configurado
	@echo "🐍 Abrindo Python shell..."
	$(VENV_PYTHON)

# ============================================================================
# MODELOS
# ============================================================================

model-download: venv ## Baixar modelo Whisper localmente
	@echo "📥 Baixando modelo Whisper: $(WHISPER_MODEL)..."
	@mkdir -p $(MODELS_DIR)
	$(VENV_PYTHON) -c "from faster_whisper import WhisperModel; WhisperModel('$(WHISPER_MODEL)', device='cpu', compute_type='int8', download_root='$(MODELS_DIR)')"
	@echo "✅ Modelo $(WHISPER_MODEL) baixado em $(MODELS_DIR)"

model-test: venv ## Testar modelo Whisper com áudio de teste
	@echo "🎤 Testando modelo Whisper..."
	@if [ -f "$(TEST_AUDIO)" ]; then \
		$(VENV_PYTHON) test-prod/test_with_audio.py; \
	else \
		echo "⚠️  Áudio de teste não encontrado: $(TEST_AUDIO)"; \
		$(VENV_PYTHON) test-prod/test_minimal.py; \
	fi

model-info: ## Mostrar informações dos modelos disponíveis
	@echo "📊 Modelos Faster-Whisper Disponíveis:"
	@echo ""
	@echo "  Modelo    VRAM    Velocidade    Qualidade"
	@echo "  ────────  ──────  ────────────  ─────────"
	@echo "  tiny      ~1 GB   ~32x          ⭐⭐"
	@echo "  base      ~1 GB   ~16x          ⭐⭐⭐"
	@echo "  small     ~2 GB   ~6x           ⭐⭐⭐⭐"
	@echo "  medium    ~5 GB   ~2x           ⭐⭐⭐⭐⭐"
	@echo "  large     ~10GB   ~1x           ⭐⭐⭐⭐⭐⭐"
	@echo ""
	@echo "💡 Modelo atual: $(WHISPER_MODEL)"
	@echo "💡 Device: $(WHISPER_DEVICE)"
	@echo ""
	@if [ -d "$(MODELS_DIR)" ]; then \
		echo "📁 Modelos baixados:"; \
		ls -lh $(MODELS_DIR) 2>/dev/null || echo "   (vazio)"; \
	else \
		echo "📁 Diretório de modelos não encontrado"; \
	fi

# ============================================================================
# TESTES
# ============================================================================

test: test-unit ## Rodar todos os testes

test-unit: venv ## Rodar testes unitários
	@echo "🧪 Rodando testes unitários..."
	$(VENV_PYTEST) tests/ -v --tb=short

test-integration: venv ## Rodar testes de integração
	@echo "🧪 Rodando testes de integração..."
	$(VENV_PYTEST) tests/ -v --tb=short -m integration

test-prod: venv ## Rodar testes de produção (test-prod/)
	@echo "🧪 Rodando testes de produção..."
	@if [ -d "test-prod" ]; then \
		echo "  → Teste mínimo..."; \
		$(VENV_PYTHON) test-prod/test_minimal.py; \
		if [ -f "$(TEST_AUDIO)" ]; then \
			echo "  → Teste com áudio..."; \
			$(VENV_PYTHON) test-prod/test_with_audio.py; \
		fi; \
	else \
		echo "⚠️  Pasta test-prod/ não encontrada"; \
	fi

test-coverage: venv ## Rodar testes com cobertura
	@echo "📊 Rodando testes com cobertura..."
	$(VENV_PYTEST) tests/ --cov=app --cov-report=html --cov-report=term
	@echo "📄 Relatório HTML: htmlcov/index.html"

# ============================================================================
# API - ENDPOINTS
# ============================================================================

api-health: ## Verificar saúde da API
	@echo "❤️  Verificando saúde da API..."
	@curl -s $(API_BASE_URL)/health | python3 -m json.tool || echo "❌ API não está respondendo"

api-languages: ## Listar idiomas suportados
	@echo "🌍 Idiomas suportados:"
	@curl -s $(API_BASE_URL)/languages | python3 -m json.tool

api-models: ## Listar modelos disponíveis
	@echo "🤖 Modelos disponíveis:"
	@curl -s $(API_BASE_URL)/models | python3 -m json.tool

api-jobs: ## Listar jobs recentes
	@echo "📋 Jobs recentes:"
	@curl -s $(API_BASE_URL)/jobs | python3 -m json.tool

api-transcribe: ## Transcrever áudio de teste (requer TEST_AUDIO)
	@echo "🎤 Transcrevendo áudio de teste..."
	@if [ -f "$(TEST_AUDIO)" ]; then \
		curl -X POST $(API_BASE_URL)/transcribe \
			-F "audio_file=@$(TEST_AUDIO)" \
			-F "language=pt" | python3 -m json.tool; \
	else \
		echo "⚠️  Áudio de teste não encontrado: $(TEST_AUDIO)"; \
	fi

# ============================================================================
# DOCKER - BUILD & DEPLOY
# ============================================================================

network: ## Criar rede Docker compartilhada
	@echo "🌐 Criando rede Docker..."
	@docker network create ytcaption_network 2>/dev/null || echo "✅ Rede já existe"

build: ## Build das imagens Docker
	@echo "🔨 Building audio-transcriber..."
	$(DOCKER_COMPOSE) build

build-no-cache: ## Build sem cache (fresh build)
	@echo "🔨 Building audio-transcriber (no cache)..."
	$(DOCKER_COMPOSE) build --no-cache

up: network ## Subir serviço em background
	@echo "🚀 Subindo audio-transcriber..."
	$(DOCKER_COMPOSE) up -d
	@echo ""
	@echo "✅ Serviço iniciado!"
	@echo "   API: $(API_BASE_URL)"
	@echo "   Logs: make logs"
	@echo "   Health: make api-health"

down: ## Parar e remover containers
	@echo "🛑 Parando audio-transcriber..."
	$(DOCKER_COMPOSE) down

restart: down up ## Reiniciar serviço

logs: ## Mostrar logs do serviço
	@echo "📜 Logs do audio-transcriber..."
	$(DOCKER_COMPOSE) logs -f --tail=100 $(DOCKER_SERVICE)

logs-api: ## Mostrar logs da API
	@echo "📜 Logs da API..."
	$(DOCKER_COMPOSE) logs -f --tail=100 audio-transcriber-service

logs-celery: ## Mostrar logs do Celery
	@echo "📜 Logs do Celery..."
	$(DOCKER_COMPOSE) logs -f --tail=100 audio-transcriber-celery

ps: ## Mostrar status dos containers
	@echo "📊 Status dos containers:"
	$(DOCKER_COMPOSE) ps

exec-api: ## Executar bash no container da API
	@echo "🐚 Abrindo shell no container da API..."
	docker exec -it audio-transcriber-api /bin/bash

exec-celery: ## Executar bash no container do Celery
	@echo "🐚 Abrindo shell no container do Celery..."
	docker exec -it audio-transcriber-celery /bin/bash

# ============================================================================
# MANUTENÇÃO
# ============================================================================

clean: ## Limpar arquivos temporários e cache
	@echo "🧹 Limpando arquivos temporários..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .coverage -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	@echo "✅ Cache limpo!"

clean-uploads: ## Limpar arquivos de upload
	@echo "🧹 Limpando uploads..."
	@if [ -d "$(UPLOADS_DIR)" ]; then \
		rm -rf $(UPLOADS_DIR)/*; \
		echo "✅ Uploads limpos!"; \
	else \
		echo "⚠️  Diretório de uploads não encontrado"; \
	fi

clean-transcriptions: ## Limpar transcrições antigas
	@echo "🧹 Limpando transcrições..."
	@if [ -d "$(TRANSCRIPTIONS_DIR)" ]; then \
		find $(TRANSCRIPTIONS_DIR) -type f -mtime +7 -delete; \
		echo "✅ Transcrições antigas removidas (>7 dias)"; \
	else \
		echo "⚠️  Diretório de transcrições não encontrado"; \
	fi

clean-models: ## Remover modelos baixados (CUIDADO!)
	@echo "⚠️  ATENÇÃO: Isso removerá todos os modelos baixados!"
	@read -p "Continuar? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf $(MODELS_DIR)/*; \
		echo "✅ Modelos removidos!"; \
	else \
		echo "❌ Operação cancelada"; \
	fi

clean-all: clean clean-uploads clean-transcriptions ## Limpar tudo (exceto modelos)
	@echo "🧹 Limpando Docker..."
	$(DOCKER_COMPOSE) down -v
	@echo "✅ Limpeza completa!"

validate: ## Validar configurações e dependências
	@echo "✅ Validando configurações..."
	@echo ""
	@echo "📁 Diretórios:"
	@mkdir -p $(LOG_DIR) $(MODELS_DIR) $(UPLOADS_DIR) $(TRANSCRIPTIONS_DIR) $(TEMP_DIR)
	@ls -ld $(LOG_DIR) $(MODELS_DIR) $(UPLOADS_DIR) $(TRANSCRIPTIONS_DIR) $(TEMP_DIR)
	@echo ""
	@echo "🐍 Python:"
	@$(VENV_PYTHON) --version
	@echo ""
	@echo "📦 Faster-Whisper:"
	@$(VENV_PYTHON) -c "import faster_whisper; print(f'  Version: {faster_whisper.__version__}')" 2>/dev/null || echo "  ⚠️  Não instalado"
	@echo ""
	@echo "🐳 Docker:"
	@docker --version
	@$(DOCKER_COMPOSE) --version
	@echo ""
	@echo "✅ Validação completa!"

# ============================================================================
# PRODUÇÃO
# ============================================================================

prod-build: ## Build otimizado para produção
	@echo "🏭 Building para produção..."
	DOCKER_BUILDKIT=1 $(DOCKER_COMPOSE) build --build-arg BUILD_ENV=production

prod-up: network prod-build ## Deploy em produção
	@echo "🚀 Deploying em produção..."
	$(DOCKER_COMPOSE) up -d
	@echo ""
	@echo "✅ Produção iniciada!"
	@make api-health

prod-logs: ## Logs de produção (últimas 500 linhas)
	@echo "📜 Logs de produção..."
	$(DOCKER_COMPOSE) logs --tail=500 $(DOCKER_SERVICE)

prod-status: ## Status de produção
	@echo "📊 Status de Produção:"
	@echo ""
	@make ps
	@echo ""
	@make api-health

# ============================================================================
# DIAGNÓSTICO
# ============================================================================

diagnose: ## Diagnóstico completo do sistema
	@echo "🔍 Diagnóstico do Audio-Transcriber..."
	@echo ""
	@echo "════════════════════════════════════════"
	@echo "1. AMBIENTE"
	@echo "════════════════════════════════════════"
	@make validate
	@echo ""
	@echo "════════════════════════════════════════"
	@echo "2. DOCKER"
	@echo "════════════════════════════════════════"
	@make ps
	@echo ""
	@echo "════════════════════════════════════════"
	@echo "3. API"
	@echo "════════════════════════════════════════"
	@make api-health
	@echo ""
	@echo "════════════════════════════════════════"
	@echo "4. MODELOS"
	@echo "════════════════════════════════════════"
	@make model-info
	@echo ""
	@echo "✅ Diagnóstico completo!"

info: ## Informações do serviço
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║              Audio-Transcriber Service Info                    ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "🎙️  Serviço: Audio Transcription com Faster-Whisper"
	@echo "🔧 Tecnologias: FastAPI + Celery + Faster-Whisper + Redis"
	@echo "🌐 API Port: $(PORT)"
	@echo "🤖 Modelo: $(WHISPER_MODEL)"
	@echo "💻 Device: $(WHISPER_DEVICE)"
	@echo ""
	@echo "📁 Diretórios:"
	@echo "  • Modelos: $(MODELS_DIR)"
	@echo "  • Uploads: $(UPLOADS_DIR)"
	@echo "  • Transcrições: $(TRANSCRIPTIONS_DIR)"
	@echo "  • Logs: $(LOG_DIR)"
	@echo ""
	@echo "🔗 Endpoints:"
	@echo "  • Health: $(API_BASE_URL)/health"
	@echo "  • Docs: $(API_BASE_URL)/docs"
	@echo "  • Transcribe: $(API_BASE_URL)/transcribe"
	@echo ""

.PHONY: venv install dev shell model-download model-test model-info \
        test test-unit test-integration test-prod test-coverage \
        api-health api-languages api-models api-jobs api-transcribe \
        network build build-no-cache up down restart \
        logs logs-api logs-celery ps exec-api exec-celery \
        clean clean-uploads clean-transcriptions clean-models clean-all validate \
        prod-build prod-up prod-logs prod-status \
        diagnose info
