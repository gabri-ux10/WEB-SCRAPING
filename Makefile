.PHONY: install test lint format migrate scrape export up down
install:
	python -m pip install -e ".[dev]"
test:
	pytest
lint:
	ruff check app tests
format:
	ruff format app tests
migrate:
	alembic upgrade head
scrape:
	python -m app.cli scrape
export:
	python -m app.cli export
up:
	docker compose up -d
down:
	docker compose down
