.PHONY: dev up down api test lint fmt migrate seed openapi-snapshot openapi-check docs-gen

up:
	docker compose -f infra/docker-compose.yml up -d --wait postgres redis mailpit

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

migrate:
	cd apps/api && uv run alembic upgrade head

seed:
	cd apps/api && uv run python scripts/seed_demo.py

openapi-snapshot:
	cd apps/api && uv run python scripts/check_openapi.py --update

openapi-check:
	cd apps/api && uv run python scripts/check_openapi.py

docs-gen:
	cd apps/api && PYTHONPATH=. uv run python scripts/gen_endpoints.py && PYTHONPATH=. uv run python scripts/gen_error_codes.py && PYTHONPATH=. uv run python scripts/gen_mocks.py
