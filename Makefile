# =============================================================================
# ForgeQA - Makefile
# =============================================================================
# Usage: make <target>
# Run `make help` to see all available targets.
# =============================================================================

SHELL := /bin/bash

# Project variables
PROJECT_NAME := forgeqa
PYTHON := python
VENV := .venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PIP := $(VENV_BIN)/pip
DIST_DIR := dist
ARTIFACTS_DIR := artifacts
SRC_DIR := src
TEST_DIR := tests
DOCS_DIR := docs

# =============================================================================
# Help (default target)
# =============================================================================
.PHONY: help
help:
	@echo "ForgeQA - Available Make Targets"
	@echo "================================="
	@echo ""
	@echo "Setup:"
	@echo "  make install            Create venv and install with dev dependencies"
	@echo "  make install-all        Install with all optional dependencies (ui, api, dev)"
	@echo ""
	@echo "Quality:"
	@echo "  make lint               Run Ruff linter"
	@echo "  make format             Apply Ruff formatting"
	@echo "  make format-check       Verify Ruff formatting"
	@echo "  make typecheck          Run MyPy"
	@echo "  make check              Run lint + format-check + typecheck"
	@echo ""
	@echo "Testing:"
	@echo "  make test               Run all tests"
	@echo "  make test-unit          Run unit tests only"
	@echo "  make test-integration   Run integration tests only"
	@echo "  make test-ui            Run UI (browser) tests only"
	@echo "  make test-api           Run API tests only"
	@echo "  make test-fast          Run tests excluding slow"
	@echo "  make test-cov           Run tests with coverage report"
	@echo ""
	@echo "Build:"
	@echo "  make build              Build wheel and sdist, then twine check"
	@echo "  make verify             Install built wheel in a clean env and verify"
	@echo "  make clean              Remove build artifacts and caches"
	@echo ""
	@echo "ADR Management:"
	@echo "  make adr-new TITLE='...'  Create a new ADR"
	@echo "  make adr-index            Regenerate the ADR index"
	@echo "  make adr-validate         Validate all ADRs"
	@echo "  make adr                  Validate + index ADRs"
	@echo ""
	@echo "CI:"
	@echo "  make ci                 Run full CI pipeline (check + test + build + verify)"
	@echo "Hooks:"
	@echo "  make hooks-install      Install pre-commit hooks"
	@echo "  make hooks-run          Run all hooks against all files"
	@echo "  make hooks-update       Update hook versions"

# =============================================================================
# Setup
# =============================================================================
.PHONY: install
install:
	@echo "Creating virtual environment..."
	$(PYTHON) -m venv $(VENV)
	@echo "Upgrading pip..."
	$(VENV_PIP) install --upgrade pip
	@echo "Installing package with dev dependencies..."
	$(VENV_PIP) install -e ".[dev]"
	@echo ""
	@echo "Done. Activate the venv with: source $(VENV_BIN)/activate"

.PHONY: install-all
install-all:
	@echo "Creating virtual environment..."
	$(PYTHON) -m venv $(VENV)
	@echo "Upgrading pip..."
	$(VENV_PIP) install --upgrade pip
	@echo "Installing package with all optional dependencies..."
	$(VENV_PIP) install -e ".[all]"
	@echo ""
	@echo "Done. Activate the venv with: source $(VENV_BIN)/activate"

# =============================================================================
# Quality
# =============================================================================
.PHONY: lint
lint:
	@echo "Running Ruff linter..."
	ruff check $(SRC_DIR) $(TEST_DIR)

.PHONY: format
format:
	@echo "Applying Ruff formatting..."
	ruff format $(SRC_DIR) $(TEST_DIR)

.PHONY: format-check
format-check:
	@echo "Checking Ruff formatting..."
	ruff format --check $(SRC_DIR) $(TEST_DIR)

.PHONY: typecheck
typecheck:
	@echo "Running MyPy type checker..."
	mypy $(SRC_DIR)

.PHONY: check
check: lint format-check typecheck
	@echo ""
	@echo "All quality checks passed."

# =============================================================================
# Testing
# =============================================================================
.PHONY: test
test:
	@echo "Running all tests..."
	pytest

.PHONY: test-unit
test-unit:
	@echo "Running unit tests..."
	pytest -m unit

.PHONY: test-integration
test-integration:
	@echo "Running integration tests..."
	pytest -m integration

.PHONY: test-ui
test-ui:
	@echo "Running UI tests..."
	pytest -m ui

.PHONY: test-api
test-api:
	@echo "Running API tests..."
	pytest -m api

.PHONY: test-fast
test-fast:
	@echo "Running tests (excluding slow)..."
	pytest -m "not slow"

.PHONY: test-cov
test-cov:
	@echo "Running tests with coverage..."
	pytest --cov=$(SRC_DIR)/$(PROJECT_NAME) --cov-report=term-missing --cov-report=html

.PHONY: verify-deps
verify-deps:
	@echo "Verifying optional dependency groups in isolated venvs..."
	./scripts/verify_deps.sh

# =============================================================================
# Build
# =============================================================================
.PHONY: build
build: clean
	@echo "Building wheel and sdist..."
	$(VENV_PYTHON) -m build
	@echo ""
	@echo "Checking package metadata..."
	$(VENV_PYTHON) -m twine check $(DIST_DIR)/*
	@echo ""
	@echo "Build artifacts:"
	@ls -la $(DIST_DIR)

.PHONY: verify
verify:
	@echo "Verifying built wheel in a clean environment..."
	@if ! ls $(DIST_DIR)/$(PROJECT_NAME)-*.whl >/dev/null 2>&1; then \
		echo "Error: No wheel found in $(DIST_DIR). Run 'make build' first."; \
		exit 1; \
	fi
	@echo "Creating temporary venv..."
	$(PYTHON) -m venv /tmp/$(PROJECT_NAME)-verify
	@echo "Installing wheel..."
	/tmp/$(PROJECT_NAME)-verify/bin/pip install $(DIST_DIR)/$(PROJECT_NAME)-*.whl
	@echo "Verifying import and version..."
	/tmp/$(PROJECT_NAME)-verify/bin/python -c "import $(PROJECT_NAME); print('Version:', $(PROJECT_NAME).__version__)"
	@echo "Cleaning up..."
	rm -rf /tmp/$(PROJECT_NAME)-verify
	@echo ""
	@echo "Wheel verification passed."

# =============================================================================
# Clean
# =============================================================================
.PHONY: clean
clean:
	@echo "Removing build artifacts and caches..."
	rm -rf $(DIST_DIR) build/
	find . -maxdepth 3 -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(ARTIFACTS_DIR) .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Clean complete."

# =============================================================================
# ADR Management
# =============================================================================
.PHONY: adr-new
adr-new:
	@if [ -z "$(TITLE)" ]; then \
		echo "Usage: make adr-new TITLE='Your decision title'"; \
		exit 1; \
	fi
	python scripts/adr.py new "$(TITLE)"

.PHONY: adr-index
adr-index:
	python scripts/adr.py index

.PHONY: adr-validate
adr-validate:
	python scripts/adr.py validate

.PHONY: adr
adr: adr-validate adr-index
	@echo "ADRs validated and indexed."

# =============================================================================
# Pre-Commit Hooks
# =============================================================================
.PHONY: hooks-install
hooks-install:
	@echo "Installing pre-commit hooks..."
	pre-commit install
	pre-commit install --hook-type commit-msg
	@echo "Hooks installed."

.PHONY: hooks-run
hooks-run:
	@echo "Running pre-commit hooks against all files..."
	pre-commit run --all-files

.PHONY: hooks-update
hooks-update:
	@echo "Updating pre-commit hook versions..."
	pre-commit autoupdate
	@echo "Run 'make hooks-run' to verify the updates."

# =============================================================================
# CI (full pipeline)
# =============================================================================
.PHONY: ci
ci: check adr test build verify verify-deps
	@echo ""
	@echo "Full CI pipeline passed."

# =============================================================================
# Aliases
# =============================================================================
.PHONY: fmt
fmt: format

.PHONY: tc
tc: typecheck

.PHONY: t
t: test
