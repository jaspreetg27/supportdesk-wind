# SupportDesk AI Development Makefile

.PHONY: format lint type test test-fast up down clean install migrate migrate-create health-check help

# Default target
help:
	@echo "Available commands:"
	@echo "  format        - Format code with black and ruff"
	@echo "  lint          - Lint code with ruff"
	@echo "  type          - Type check with mypy"
	@echo "  test          - Run all tests"
	@echo "  test-fast     - Run fast tests only"
	@echo "  up            - Start services with docker-compose"
	@echo "  down          - Stop services"
	@echo "  clean         - Stop services and clean volumes"
	@echo "  install       - Install package in development mode"
	@echo "  migrate       - Run database migrations"
	@echo "  migrate-create - Create new migration (use: make migrate-create name=migration_name)"
	@echo "  health-check  - Test health endpoint"

format:
	black src/ tests/
	ruff format src/ tests/

lint:
	ruff check src/ tests/

type:
	mypy src/

test:
	pytest -v

test-fast:
	pytest -m "not slow" -q

up:
	docker-compose up -d

down:
	docker-compose down

clean:
	docker-compose down -v
	docker system prune -f

install:
	pip install -e .[dev]

migrate:
	alembic upgrade head

migrate-create:
	@if [ -z "$(name)" ]; then \
		echo "Error: Migration name required. Use: make migrate-create name=migration_name"; \
		exit 1; \
	fi
	alembic revision --autogenerate -m "$(name)"

health-check:
	@echo "Testing health endpoint..."
	@curl -f http://localhost:8000/healthz || echo "Health check failed"
	@echo ""
	@echo "Testing root endpoint..."
	@curl -f http://localhost:8000/ || echo "Root endpoint failed"
