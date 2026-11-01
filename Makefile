# Agentic Quality Platform — developer tasks.
# Provisioning lives in scripts/bootstrap.sh (no custom .devcontainer); the rest
# are thin wrappers so CLAUDE.md, CI, and local runs stay consistent.

.DEFAULT_GOAL := help
.PHONY: help setup install run test lint format typecheck check ci clean

# Feature file or directory to run (override: make run FEATURE=features/refund.feature).
FEATURE ?= features/
PYTHON  ?= python

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## One-time provisioning for a fresh Codespace (Node, Playwright MCP + browser deps, Python deps)
	bash scripts/bootstrap.sh

install: ## Install the package (editable) with dev extras — Python deps only
	$(PYTHON) -m pip install -e ".[dev]"

run: ## Run a feature file or directory (make run FEATURE=<path>)
	aqp run $(FEATURE)

test: ## Run the unit suite (MCP client and agents are mocked — no live browser or model)
	$(PYTHON) -m pytest

lint: ## Lint + enforce the import-boundary contracts
	$(PYTHON) -m ruff check .
	lint-imports

format: ## Auto-format and sort imports
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --select I --fix .

typecheck: ## Type-check src/ with mypy
	$(PYTHON) -m mypy

check: ci ## Alias for `ci`

ci: lint typecheck test ## Lint + typecheck + unit tests — the full gate. Run before calling work done

clean: ## Remove caches and generated artifacts
	rm -rf artifacts .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
