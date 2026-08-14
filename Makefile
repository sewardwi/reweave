.DEFAULT_GOAL := help
SHELL := /bin/bash

# Keep these in sync with .python-version, .nvmrc, and .github/workflows/ci.yml.
PY := uv run
COMPOSE := docker compose -f infra/docker-compose.dev.yml

.PHONY: help setup dev down lint fmt typecheck test bench repo-eval check clean

help: ## Show available targets
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Install toolchains and all workspace dependencies
	uv sync --all-packages
	@command -v pnpm >/dev/null || corepack enable 2>/dev/null || npm install -g pnpm@9
	cd apps/web && pnpm install
	$(PY) pre-commit install --hook-type pre-commit --hook-type commit-msg

dev: ## Bring up postgres(pgvector) + redis + api + worker
	$(COMPOSE) up --build -d
	@echo "api    → http://localhost:8000"
	@echo "db     → postgres://reweave:reweave@localhost:5432/reweave"
	@echo "logs   → $(COMPOSE) logs -f"

down: ## Stop the dev stack and remove volumes
	$(COMPOSE) down -v

lint: ## Lint Python and web
	$(PY) ruff check .
	$(PY) ruff format --check .
	cd apps/web && pnpm lint

fmt: ## Auto-format everything
	$(PY) ruff check --fix .
	$(PY) ruff format .
	cd apps/web && pnpm format

typecheck: ## Strict type checking, Python and web
	$(PY) pyright
	cd apps/web && pnpm typecheck

test: ## Run the test suites
	$(PY) pytest

bench: ## Pair benchmark — the CI merge gate (D12)
	$(PY) python benchmarks/run_bench.py

repo-eval: ## Repo-level eval — the ship gate (D12). Slow; needs network on first run.
	$(PY) python benchmarks/run_repo_eval.py

check: lint typecheck test bench ## Everything CI runs

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache reports
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
