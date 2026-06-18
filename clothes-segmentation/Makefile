# Clothes Segmentation API — Makefile (Git Bash / WSL)

SHELL := /bin/bash

PYTHON  ?= python
PIP     ?= pip
NODE    ?= node

PROJECT_ROOT := $(shell pwd)
SRC_DIR      := src/clothes_segmentation
CHECKPOINTS  := checkpoints
EXTERNAL     := external

CHECKPOINT_FILES := $(CHECKPOINTS)/groundingdino_swint_ogc.pth \
                    $(CHECKPOINTS)/sam2_hiera_large.pt \
                    $(CHECKPOINTS)/sam2_hiera_tiny.pt

.PHONY: all install start stop test clean checkpoints help lint format deps-check

all: help

help:
	@echo "========================================="
	@echo "  Clothes Segmentation — Makefile"
	@echo "========================================="
	@echo ""
	@echo "  Commands:"
	@echo "    make install       Install all Python dependencies"
	@echo "    make start         Start API server (port 8001)"
	@echo "    make stop          Stop API server"
	@echo "    make test          Run regression tests against API"
	@echo "    make lint          Run ruff linter"
	@echo "    make format        Format code with ruff"
	@echo "    make deps-check    Verify all dependencies installed"
	@echo "    make checkpoints   Check if checkpoint files exist"
	@echo "    make clean         Remove __pycache__, .pyc, temp files"
	@echo "    make reset         Full clean + reinstall dependencies"
	@echo "    make docker-build  Build Docker image"
	@echo "    make docker-run    Run Docker container"
	@echo ""

install:
	@echo "[INSTALL] Installing dependencies..."
	$(PIP) install -r requirements.txt
	@echo "[INSTALL] Done."

deps-check:
	@echo "[DEPS] Checking dependencies..."
	$(PYTHON) -c "import fastapi, uvicorn, torch, torchvision, cv2, supervision, PIL, numpy, h5py, pydantic" 2>/dev/null \
		&& echo "[DEPS] All OK" \
		|| echo "[DEPS] MISSING — run 'make install'"

lint:
	@echo "[LINT] Running ruff..."
	ruff check $(SRC_DIR) || true

format:
	@echo "[FORMAT] Running ruff format..."
	ruff format $(SRC_DIR) || true

checkpoints:
	@echo "[CHECKPOINTS] Verifying model files..."
	@for f in $(CHECKPOINT_FILES); do \
		if [ -f "$$f" ]; then \
			echo "  OK: $$f"; \
		else \
			echo "  MISSING: $$f"; \
		fi; \
	done

start:
	@echo "[START] Launching API server on port 8001..."
	@cd src && PYTHONPATH=. $(PYTHON) -m clothes_segmentation.api.server

stop:
	@echo "[STOP] Killing Python processes..."
	@pkill -f "clothes_segmentation.api.server" || true

test: start
	@sleep 45
	@echo "[TEST] Running regression tests..."
	$(PYTHON) tests/test_api.py
	@make stop

clean:
	@echo "[CLEAN] Removing cache files..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "[CLEAN] Done."

reset: clean install

docker-build:
	@echo "[DOCKER] Building image..."
	docker build -t clothes-segmentation:latest -f docker/Dockerfile .

docker-run:
	@echo "[DOCKER] Running container on port 8001..."
	docker run --rm -p 8001:8001 clothes-segmentation:latest
