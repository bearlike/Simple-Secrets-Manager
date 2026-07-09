# Simple Secrets Manager — developer front door.
# Thin delegation only: every target shells out to the script that already owns
# the logic (scripts/*.sh, uv, npm). Keep behaviour in those scripts, not here.
.DEFAULT_GOAL := help

.PHONY: help check fix test lint-imports precommit-install stack build frontend

help: ## Show this help
	@echo "Simple Secrets Manager — make targets:"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

check: ## Full quality gate (ruff, pylint, mypy, import-linter, pytest)
	./scripts/quality.sh check

fix: ## Auto-fix formatting/lint, then run the full gate
	./scripts/quality.sh fix

test: ## Run the pytest suite
	uv run pytest -q

lint-imports: ## Check the import-linter architecture contracts
	uv run lint-imports

precommit-install: ## Install the repo git hooks (core.hooksPath=.githooks)
	./scripts/install-git-hooks.sh

stack: ## Build + start the full Docker stack
	./scripts/deploy_stack.sh

build: ## Build the versioned Docker image
	./scripts/build.sh

frontend: ## Lint + build the React admin console
	cd frontend && npm run lint && npm run build
