# Audio Voice Service - Makefile
# Comandos para facilitar desenvolvimento e deploy

.PHONY: help cleanup rebuild restart logs logs-api logs-celery logs-vram status health test

# Cores para output
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Mostra esta mensagem de ajuda
	@echo "$(GREEN)Audio Voice Service - Comandos Disponíveis:$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""

cleanup: ## Limpa containers, imagens e volumes órfãos
	@echo "$(YELLOW)🧹 Limpando audio-voice...$(NC)"
	@bash ../../scripts/docker-cleanup-audio-voice.sh

rebuild: ## Rebuild completo sem cache (cleanup + build + up)
	@echo "$(YELLOW)🔨 Rebuild completo...$(NC)"
	@bash ../../scripts/rebuild-audio-voice.sh

rebuild-fast: ## Rebuild rápido COM cache (down + build + up)
	@echo "$(YELLOW)⚡ Rebuild rápido (com cache)...$(NC)"
	@docker compose down
	@docker compose build
	@docker compose up -d
	@echo "$(GREEN)✅ Rebuild rápido concluído!$(NC)"

restart: ## Restart dos containers (NÃO recarrega .env!)
	@echo "$(YELLOW)🔄 Restart containers...$(NC)"
	@docker compose restart
	@echo "$(GREEN)✅ Containers reiniciados$(NC)"

down: ## Para todos os containers
	@echo "$(YELLOW)🛑 Parando containers...$(NC)"
	@docker compose down
	@echo "$(GREEN)✅ Containers parados$(NC)"

up: ## Sobe containers (se já buildados)
	@echo "$(YELLOW)🚀 Subindo containers...$(NC)"
	@docker compose up -d
	@echo "$(GREEN)✅ Containers rodando$(NC)"

logs: ## Mostra logs de todos os containers (tail -f)
	@docker compose logs -f --tail=100

logs-api: ## Mostra logs apenas da API
	@docker logs audio-voice-api -f --tail=100

logs-celery: ## Mostra logs apenas do Celery Worker
	@docker logs audio-voice-celery -f --tail=100

logs-vram: ## Filtra logs relacionados a VRAM/GPU
	@echo "$(YELLOW)📊 Logs de VRAM/GPU:$(NC)"
	@docker logs audio-voice-celery 2>&1 | grep -E "(VRAM|GPU|CUDA|carregando|descarregando|LOW_VRAM)" --color=always | tail -50

status: ## Mostra status dos containers
	@echo "$(GREEN)📊 Status dos Containers:$(NC)"
	@docker ps --filter "name=audio-voice" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

health: ## Verifica health checks dos containers
	@echo "$(GREEN)🏥 Health Checks:$(NC)"
	@echo ""
	@echo -n "API:    "
	@docker inspect audio-voice-api --format='{{.State.Health.Status}}' 2>/dev/null || echo "no healthcheck"
	@echo -n "Celery: "
	@docker inspect audio-voice-celery --format='{{.State.Health.Status}}' 2>/dev/null || echo "no healthcheck"
	@echo ""

test: ## Executa testes básicos de validação
	@echo "$(YELLOW)🧪 Executando testes...$(NC)"
	@bash ../../scripts/test-single-container.sh

vram-stats: ## Mostra estatísticas de VRAM
	@echo "$(GREEN)📊 VRAM Stats (nvidia-smi):$(NC)"
	@docker exec audio-voice-celery nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv,noheader 2>/dev/null || echo "$(RED)❌ GPU não acessível$(NC)"
	@echo ""
	@echo "$(GREEN)📊 VRAM Stats (API endpoint):$(NC)"
	@curl -s http://localhost:8005/admin/vram 2>/dev/null | jq '.' || echo "$(RED)❌ Endpoint não disponível$(NC)"

shell-api: ## Abre shell no container da API
	@docker exec -it audio-voice-api /bin/bash

shell-celery: ## Abre shell no container do Celery
	@docker exec -it audio-voice-celery /bin/bash

env-check: ## Verifica variáveis de ambiente importantes
	@echo "$(GREEN)🔍 Environment Variables Check:$(NC)"
	@echo ""
	@echo "📄 Arquivo .env:"
	@grep -E "^(LOW_VRAM|F5TTS_DEVICE|XTTS_DEVICE|CUDA_VISIBLE_DEVICES)" .env || echo "   $(YELLOW)⚠️  Variáveis não encontradas$(NC)"
	@echo ""
	@echo "🐳 Container Celery:"
	@docker inspect audio-voice-celery --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep -E "(LOW_VRAM|F5TTS_DEVICE|XTTS_DEVICE|CUDA)" || echo "   $(YELLOW)⚠️  Variáveis não encontradas$(NC)"

# Atalhos
c: cleanup ## Atalho para cleanup
r: rebuild ## Atalho para rebuild
s: status  ## Atalho para status
l: logs    ## Atalho para logs
h: health  ## Atalho para health
