.PHONY: help install run dev worker lint test clean docker-build docker-up docker-down

help:
	@echo "Available commands:"
	@echo "  make install     - Install dependencies"
	@echo "  make run         - Run API server"
	@echo "  make dev         - Run API with hot reload"
	@echo "  make worker      - Run Celery worker"
	@echo "  make test        - Run tests"
	@echo "  make lint        - Run linting"
	@echo "  make clean       - Clean temporary files"
	@echo "  make docker-build - Build Docker images"
	@echo "  make docker-up   - Start all services with Docker"
	@echo "  make docker-down - Stop all services with Docker"

install:
	pip install -r requirements.txt

run:
	python run.py

dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8007 --reload

worker:
	celery -A app.infrastructure.celery_config.celery_app worker --loglevel=info --concurrency=1 --queues=audio_generation_queue

test:
	python -m pytest tests/ -v --tb=short

lint:
	ruff check app/ tests/ || true

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf data/temp/* data/outputs/*

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down
