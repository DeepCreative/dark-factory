.PHONY: help ci lint format format-check test dev dev-down install install-dev clean build check-internal

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

ci: lint format-check test check-internal ## Full CI pipeline

lint: ## Run ruff linter
	ruff check dark_factory/ tests/

format: ## Auto-format code
	ruff format dark_factory/ tests/
	ruff check --fix dark_factory/ tests/

format-check: ## Check formatting
	ruff format --check dark_factory/ tests/

test: ## Run tests with coverage
	pytest --cov=dark_factory --cov-report=xml --cov-report=term-missing tests/

dev: ## Start local dev server with hot reload
	docker compose -f docker-compose.dev.yaml up --build -d

dev-logs: ## Tail dev container logs
	docker compose -f docker-compose.dev.yaml logs -f

dev-down: ## Stop dev containers
	docker compose -f docker-compose.dev.yaml down

install: ## Install package
	pip install -e .

install-dev: ## Install with dev dependencies
	pip install -e ".[dev]"
	pip install -r requirements-service.txt

clean: ## Remove build artifacts
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache __pycache__ coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

build: ## Build package
	python -m build

check-internal: ## Verify cluster-only (no Ingress/ALB/LB)
	@if grep -rq 'kind: Ingress\|kind: LoadBalancer\|alb.ingress' k8s/ 2>/dev/null; then \
		echo "ERROR: Found external exposure resources"; exit 1; \
	else \
		echo "OK: cluster-only"; \
	fi
