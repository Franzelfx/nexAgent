.PHONY: dev test migrate lint format

# Start dev environment (DB + API)
dev:
	docker compose -f docker-compose.dev.yml up --build

# Run tests
test:
	PYTHONPATH=src pytest tests/ -v

# Run Alembic migrations
migrate:
	PYTHONPATH=src alembic upgrade head

# Create a new migration
migration:
	PYTHONPATH=src alembic revision --autogenerate -m "$(msg)"

# Lint
lint:
	ruff check src/ tests/

# Format
format:
	ruff format src/ tests/

# Install dev dependencies
install:
	pip install -e ".[dev]"
