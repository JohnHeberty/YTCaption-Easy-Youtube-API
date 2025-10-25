.PHONY: help build up down restart logs clean test lint format

# Variáveis
COMPOSE_FILE = docker-compose.yml
SERVICES = video-downloader audio-normalization audio-transcriber

help: ## Mostra esta ajuda
	@echo "Comandos disponíveis:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Constrói todas as imagens Docker
	docker-compose -f $(COMPOSE_FILE) build --no-cache
	@echo "✅ Imagens construídas com sucesso!"

up: ## Inicia todos os serviços
	docker network create ytcaption-network 2>/dev/null || true
	docker-compose -f $(COMPOSE_FILE) up -d
	@echo "✅ Serviços iniciados!"
	@echo "🔗 Video Downloader: http://localhost:8000"
	@echo "🔗 Audio Normalization: http://localhost:8001"  
	@echo "🔗 Audio Transcriber: http://localhost:8002"

down: ## Para todos os serviços
	docker-compose -f $(COMPOSE_FILE) down
	@echo "🛑 Serviços parados!"

restart: down up ## Reinicia todos os serviços

logs: ## Mostra logs de todos os serviços
	docker-compose -f $(COMPOSE_FILE) logs -f

logs-video: ## Logs do Video Downloader
	docker-compose -f $(COMPOSE_FILE) logs -f video-downloader

logs-audio: ## Logs do Audio Normalization
	docker-compose -f $(COMPOSE_FILE) logs -f audio-normalization

logs-transcriber: ## Logs do Audio Transcriber
	docker-compose -f $(COMPOSE_FILE) logs -f audio-transcriber

status: ## Mostra status dos serviços
	docker-compose -f $(COMPOSE_FILE) ps
	@echo ""
	@echo "Health Checks:"
	@curl -s http://localhost:8000/health | jq . 2>/dev/null || echo "❌ Video Downloader (8000) não acessível"
	@curl -s http://localhost:8001/health | jq . 2>/dev/null || echo "❌ Audio Normalization (8001) não acessível"
	@curl -s http://localhost:8002/health | jq . 2>/dev/null || echo "❌ Audio Transcriber (8002) não acessível"

clean: ## Remove containers, volumes e imagens não utilizadas
	docker-compose -f $(COMPOSE_FILE) down -v
	docker system prune -f
	docker volume prune -f
	@echo "🧹 Limpeza concluída!"

clean-all: ## Remove tudo (incluindo imagens)
	docker-compose -f $(COMPOSE_FILE) down -v --rmi all
	docker system prune -af
	docker volume prune -f
	@echo "🧹 Limpeza completa concluída!"

test: ## Executa testes básicos nos endpoints
	@echo "🧪 Testando endpoints..."
	@echo "Video Downloader (8000):"
	@curl -s -o /dev/null -w "  Status: %{http_code}\n" http://localhost:8000/health || echo "  ❌ Falhou"
	@echo "Audio Normalization (8001):"
	@curl -s -o /dev/null -w "  Status: %{http_code}\n" http://localhost:8001/health || echo "  ❌ Falhou"
	@echo "Audio Transcriber (8002):"
	@curl -s -o /dev/null -w "  Status: %{http_code}\n" http://localhost:8002/health || echo "  ❌ Falhou"

lint: ## Executa linting nos arquivos Python
	@echo "🔍 Executando linting..."
	@for service in $(SERVICES); do \
		echo "Verificando services/$$service/app/"; \
		find services/$$service/app/ -name "*.py" -exec python -m py_compile {} \; || true; \
	done
	@echo "✅ Linting concluído!"

format: ## Formata código Python com black
	@echo "🎨 Formatando código..."
	@for service in $(SERVICES); do \
		echo "Formatando services/$$service/app/"; \
		find services/$$service/app/ -name "*.py" -exec black --line-length 88 {} \; 2>/dev/null || true; \
	done
	@echo "✅ Formatação concluída!"

dev: ## Inicia em modo desenvolvimento (com logs)
	docker network create ytcaption-network 2>/dev/null || true
	docker-compose -f $(COMPOSE_FILE) up --build
	
dev-bg: ## Inicia em modo desenvolvimento (background)
	docker network create ytcaption-network 2>/dev/null || true
	docker-compose -f $(COMPOSE_FILE) up -d --build
	@echo "🔧 Modo desenvolvimento ativo!"
	@echo "📊 Para ver logs: make logs"

backup: ## Faz backup dos dados
	@echo "💾 Criando backup..."
	@mkdir -p backups/$(shell date +%Y%m%d_%H%M%S)
	@for service in $(SERVICES); do \
		if [ -d "services/$$service/uploads" ]; then \
			cp -r services/$$service/uploads backups/$(shell date +%Y%m%d_%H%M%S)/$$service-uploads/ 2>/dev/null || true; \
		fi; \
		if [ -d "services/$$service/processed" ]; then \
			cp -r services/$$service/processed backups/$(shell date +%Y%m%d_%H%M%S)/$$service-processed/ 2>/dev/null || true; \
		fi; \
	done
	@echo "✅ Backup criado em backups/$(shell date +%Y%m%d_%H%M%S)/"

install-deps: ## Instala dependências do sistema
	@echo "📦 Instalando dependências..."
	@command -v docker >/dev/null 2>&1 || { echo "❌ Docker não encontrado. Instale o Docker primeiro."; exit 1; }
	@command -v docker-compose >/dev/null 2>&1 || { echo "❌ Docker Compose não encontrado. Instale o Docker Compose primeiro."; exit 1; }
	@command -v curl >/dev/null 2>&1 || { echo "❌ curl não encontrado. Instale curl primeiro."; exit 1; }
	@echo "✅ Todas as dependências estão instaladas!"

redis-check: ## Verifica conectividade com Redis
	@echo "🔍 Verificando Redis em 192.168.18.110:6379..."
	@redis-cli -h 192.168.18.110 -p 6379 ping 2>/dev/null && echo "✅ Redis conectado!" || echo "❌ Redis não acessível"

setup: install-deps redis-check ## Setup inicial completo
	@echo "🚀 Configuração inicial..."
	@mkdir -p services/video-downloader/{cache,logs}
	@mkdir -p services/audio-normalization/{uploads,processed,temp,logs}
	@mkdir -p services/audio-transcriber/{uploads,transcriptions,models,temp,logs}
	@mkdir -p backups
	docker network create ytcaption-network 2>/dev/null || true
	@echo "✅ Setup concluído! Execute 'make up' para iniciar os serviços."

stats: ## Mostra estatísticas dos serviços
	@echo "📊 Estatísticas dos Serviços:"
	@echo ""
	@echo "Video Downloader:"
	@curl -s http://localhost:8000/admin/stats | jq . 2>/dev/null || echo "  Não disponível"
	@echo ""
	@echo "Audio Normalization:"  
	@curl -s http://localhost:8001/admin/stats | jq . 2>/dev/null || echo "  Não disponível"
	@echo ""
	@echo "Audio Transcriber:"
	@curl -s http://localhost:8002/admin/stats | jq . 2>/dev/null || echo "  Não disponível"

cleanup-cache: ## Limpa cache de todos os serviços
	@echo "🧹 Limpando cache dos serviços..."
	@curl -X DELETE http://localhost:8000/admin/cache 2>/dev/null || echo "Video Downloader não acessível"
	@curl -X DELETE http://localhost:8001/admin/cache 2>/dev/null || echo "Audio Normalization não acessível"  
	@curl -X DELETE http://localhost:8002/admin/cache 2>/dev/null || echo "Audio Transcriber não acessível"
	@echo "✅ Cache limpo!"

monitor: ## Mostra logs em tempo real com filtros
	@echo "📱 Monitoramento em tempo real (Ctrl+C para sair)..."
	docker-compose -f $(COMPOSE_FILE) logs -f | grep -E "(ERROR|WARN|INFO.*job|health)"