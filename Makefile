.PHONY: dev up down api test lint fmt

up:
	docker compose -f infra/docker-compose.yml up -d --wait postgres redis

down:
	docker compose -f infra/docker-compose.yml down

api:
	cd apps/api && uv run uvicorn app.main:app --reload

dev: up api

test:
	cd apps/api && uv run pytest -q

lint:
	cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run mypy app

fmt:
	cd apps/api && uv run ruff check --fix . && uv run ruff format .
