PYTHON := .venv/bin/python
PIP := .venv/bin/pip
UVICORN := .venv/bin/uvicorn
PYTEST := .venv/bin/pytest
RUFF := .venv/bin/ruff

.PHONY: help setup install run test lint format check db-up db-down db-logs migrate clean

help:
	@echo "Available commands:"
	@echo "  make setup     Create virtual environment and install dependencies"
	@echo "  make install   Install project dependencies"
	@echo "  make run       Start the FastAPI app locally"
	@echo "  make test      Run tests"
	@echo "  make lint      Run lint checks"
	@echo "  make format    Format and fix lint issues"
	@echo "  make check     Run lint and tests"
	@echo "  make db-up     Start Postgres"
	@echo "  make db-down   Stop Postgres"
	@echo "  make db-logs   Follow Postgres logs"
	@echo "  make migrate   Run SQL migrations"
	@echo "  make clean     Remove generated cache files"

setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

install:
	$(PYTHON) -m pip install -e ".[dev]"

run:
	$(UVICORN) app.main:app --reload

test:
	$(PYTEST)
	$(MAKE) clean

lint:
	$(RUFF) check .

format:
	$(RUFF) check . --fix

check: lint test

db-up:
	docker compose up -d database

db-down:
	docker compose down

db-logs:
	docker compose logs -f database

migrate:
	$(PYTHON) -c "from app.core.migrations import run_migrations; run_migrations()"

clean:
	rm -rf .pytest_cache .ruff_cache web_backend.egg-info
	find app tests migrations -type d -name __pycache__ -prune -exec rm -rf {} +
