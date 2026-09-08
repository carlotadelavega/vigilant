OLLAMA_MODEL ?= qwen2.5:14b

.PHONY: install dev test lint format up up-ui ollama-model down

install:
	uv sync

dev:
	uv run uvicorn vigilant.main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest -v

lint:
	uv run ruff check .
	uv run mypy src

format:
	uv run ruff format .
	uv run ruff check --fix .

up:
	docker compose up -d

up-ui:
	docker compose -f docker-compose.yml -f docker-compose.dev-ui.yml up -d

ollama-model:
	@models="$$(docker exec vigilant-ollama ollama list)"; \
	printf '%s\n' "$$models"; \
	if ! printf '%s\n' "$$models" | tail -n +2 | grep -q '[^[:space:]]'; then \
		docker exec -it vigilant-ollama ollama pull $(OLLAMA_MODEL); \
	fi

down:
	docker compose -f docker-compose.yml -f docker-compose.dev-ui.yml down
