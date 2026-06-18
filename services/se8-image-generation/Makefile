SERVICE_NAME := se8-image-generation
PORT := 8008
DC := docker compose
DC_FILE := docker/docker-compose.yml
DC_ARGS := --env-file .env

.PHONY: help build up down restart logs status health dev stop clean rebuild test lint

help:
	@echo "Targets:"
	@echo "  build      - Build images (GPU)"
	@echo "  up         - Start containers (GPU)"
	@echo "  down       - Stop containers"
	@echo "  restart    - down + up"
	@echo "  logs       - View logs"
	@echo "  status     - Container status"
	@echo "  health     - Health check"
	@echo "  rebuild    - Build (no-cache) + up"
	@echo "  clean      - Remove containers, images, volumes"
	@echo "  dev        - Local dev (uvicorn, no Docker)"
	@echo "  test       - Run tests"
	@echo "  lint       - AST parse check"

build:
	cd .. && $(DC) -f $(SERVICE_NAME)/$(DC_FILE) $(DC_ARGS) build

up:
	cd .. && $(DC) -f $(SERVICE_NAME)/$(DC_FILE) $(DC_ARGS) up -d

down:
	cd .. && $(DC) -f $(SERVICE_NAME)/$(DC_FILE) $(DC_ARGS) down

restart: down up

logs:
	cd .. && $(DC) -f $(SERVICE_NAME)/$(DC_FILE) $(DC_ARGS) logs -f --tail=100

status:
	cd .. && $(DC) -f $(SERVICE_NAME)/$(DC_FILE) $(DC_ARGS) ps

health:
	@curl -sf http://localhost:$(PORT)/health && echo "" || echo "FAIL"

dev:
	uvicorn app.main:app --host 0.0.0.0 --port $(PORT) --reload

stop:
	cd .. && $(DC) -f $(SERVICE_NAME)/$(DC_FILE) $(DC_ARGS) stop

clean:
	cd .. && $(DC) -f $(SERVICE_NAME)/$(DC_FILE) $(DC_ARGS) down -v --rmi local

rebuild:
	cd .. && $(DC) -f $(SERVICE_NAME)/$(DC_FILE) $(DC_ARGS) build --no-cache && \
	$(DC) -f $(SERVICE_NAME)/$(DC_FILE) $(DC_ARGS) up -d

test:
	python -m pytest tests/ -v --tb=short

lint:
	@echo "=== AST Parse Check ==="
	@python -c "import ast; [ast.parse(open(f).read()) for f in __import__('glob').glob('app/**/*.py', recursive=True)]" && echo "OK" || echo "FAIL"
