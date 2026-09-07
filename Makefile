.PHONY: install dev test lint format migrate

install:
	uv sync

dev:
	uv run uvicorn vigilant.api.router:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest -v

lint:
	uv run ruff check .
	uv run mypy src

format:
	uv run ruff format .
	uv run ruff check --fix .

migrate:
	uv run alembic upgrade head