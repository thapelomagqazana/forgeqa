# =============================================================================
# ForgeQA Reference Application - Makefile
# =============================================================================
# Usage: make <target>
# Run `make help` to see all available targets.
# =============================================================================

SHELL := /bin/bash

APP_NAME := forgeqa-reference-app
PYTHON := python
VENV := .venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PIP := $(VENV_BIN)/pip
HOST := 127.0.0.1
PORT := 8000
BASE_URL := http://$(HOST):$(PORT)

# =============================================================================
# Help (default target)
# =============================================================================
.PHONY: help
help:
	@echo "ForgeQA Reference Application - Available Make Targets"
	@echo "======================================================"
	@echo ""
	@echo "Setup:"
	@echo "  make install        Create venv and install dependencies"
	@echo ""
	@echo "Run:"
	@echo "  make run            Start the server at $(BASE_URL)"
	@echo "  make run-reload     Start the server with auto-reload (development)"
	@echo ""
	@echo "Test:"
	@echo "  make test           Run all tests"
	@echo "  make test-cov       Run tests with coverage"
	@echo ""
	@echo "Utilities:"
	@echo "  make reset          Reset the in-memory store via POST /api/admin/reset"
	@echo "  make health         Check the health endpoint"
	@echo "  make clean          Remove venv, caches, and build artifacts"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build   Build the Docker image"
	@echo "  make docker-up      Start the app via docker-compose"
	@echo "  make docker-down    Stop the docker-compose stack"
	@echo "  make docker-logs    View docker-compose logs"
	@echo ""
	@echo "Base URL: $(BASE_URL)"
	@echo "API Docs: $(BASE_URL)/docs"

# =============================================================================
# Setup
# =============================================================================
.PHONY: install
install:
	@echo "Creating virtual environment..."
	$(PYTHON) -m venv $(VENV)
	@echo "Upgrading pip..."
	$(VENV_PIP) install --upgrade pip
	@echo "Installing dependencies..."
	$(VENV_PIP) install -e ".[dev]"
	@echo ""
	@echo "Done. Activate the venv with: source $(VENV_BIN)/activate"

# =============================================================================
# Run
# =============================================================================
.PHONY: run
run:
	@echo "Starting server at $(BASE_URL)..."
	@echo "Press Ctrl+C to stop."
	$(VENV_BIN)/uvicorn app.main:app --host $(HOST) --port $(PORT)

.PHONY: run-reload
run-reload:
	@echo "Starting server with auto-reload at $(BASE_URL)..."
	@echo "Press Ctrl+C to stop."
	$(VENV_BIN)/uvicorn app.main:app --host $(HOST) --port $(PORT) --reload

# =============================================================================
# Test
# =============================================================================
.PHONY: test
test:
	@echo "Running all tests..."
	$(VENV_BIN)/pytest tests/ -v

.PHONY: test-cov
test-cov:
	@echo "Running tests with coverage..."
	$(VENV_BIN)/pytest tests/ -v --cov=app --cov-report=term-missing

# =============================================================================
# Utilities
# =============================================================================
.PHONY: reset
reset:
	@echo "Resetting in-memory store..."
	@curl -s -X POST $(BASE_URL)/api/admin/reset | python -m json.tool || \
		(echo "Error: Could not reach $(BASE_URL). Is the server running?"; exit 1)

.PHONY: health
health:
	@echo "Checking health endpoint..."
	@curl -s $(BASE_URL)/api/health | python -m json.tool || \
		(echo "Error: Could not reach $(BASE_URL). Is the server running?"; exit 1)

.PHONY: clean
clean:
	@echo "Removing venv, caches, and build artifacts..."
	rm -rf $(VENV) .pytest_cache .coverage htmlcov/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Clean complete."

# =============================================================================
# Docker
# =============================================================================
.PHONY: docker-build
docker-build:
	@echo "Building Docker image..."
	docker compose build

.PHONY: docker-up
docker-up:
	@echo "Starting docker-compose stack..."
	docker compose up -d
	@echo ""
	@echo "Server available at $(BASE_URL)"
	@echo "API Docs: $(BASE_URL)/docs"
	@echo "View logs: make docker-logs"

.PHONY: docker-down
docker-down:
	@echo "Stopping docker-compose stack..."
	docker compose down

.PHONY: docker-logs
docker-logs:
	docker compose logs -f
