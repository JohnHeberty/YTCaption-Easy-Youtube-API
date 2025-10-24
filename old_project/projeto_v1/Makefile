# Makefile para facilitar comandos comuns

.PHONY: help install dev-install test coverage lint format clean run docker-build docker-up docker-down docker-logs

help: ## Mostra esta mensagem de ajuda
	@echo "Comandos disponíveis:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Instala dependências de produção
	pip install -r requirements.txt

dev-install: ## Instala dependências de desenvolvimento
	pip install -r requirements.txt
	pip install pytest pytest-asyncio pytest-cov black flake8 mypy

test: ## Executa testes
	pytest -v

coverage: ## Executa testes com coverage
	pytest --cov=src --cov-report=html --cov-report=term

lint: ## Verifica code style
	flake8 src/ tests/
	mypy src/

format: ## Formata código com black
	black src/ tests/

clean: ## Remove arquivos temporários
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	rm -rf temp/

run: ## Executa a aplicação localmente
	uvicorn src.presentation.api.main:app --reload --host 0.0.0.0 --port 8000

docker-build: ## Build da imagem Docker
	docker-compose build

docker-up: ## Inicia containers
	docker-compose up -d

docker-down: ## Para containers
	docker-compose down

docker-logs: ## Mostra logs dos containers
	docker-compose logs -f

docker-restart: ## Reinicia containers
	docker-compose restart

docker-clean: ## Remove containers e volumes
	docker-compose down -v
	docker system prune -f

setup: ## Setup inicial do projeto
	cp .env.example .env
	mkdir -p temp logs
	@echo "✅ Setup concluído! Edite o arquivo .env conforme necessário."

all: clean lint test ## Executa limpeza, lint e testes
