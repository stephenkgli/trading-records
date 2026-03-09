.PHONY: dev dev-backend dev-frontend test test-backend test-frontend lint lint-backend lint-frontend format build migrate

# --- Development ---

dev: dev-backend dev-frontend

dev-backend:
	uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

# --- Testing ---

test: test-backend test-frontend

test-backend:
	uv run pytest tests/ -v

test-backend-cov:
	uv run pytest tests/ --cov=backend --cov-report=term-missing

test-frontend:
	cd frontend && npm test

# --- Linting ---

lint: lint-backend lint-frontend

lint-backend:
	uv run ruff check backend/
	uv run ruff format --check backend/

lint-frontend:
	cd frontend && npx eslint src/
	cd frontend && npx prettier --check "src/**/*.{ts,tsx,css}"

# --- Formatting ---

format:
	uv run ruff check --fix backend/
	uv run ruff format backend/
	cd frontend && npx prettier --write "src/**/*.{ts,tsx,css}"

# --- Build ---

build:
	docker compose build

build-frontend:
	cd frontend && npm run build

# --- Database ---

migrate:
	uv run alembic upgrade head

migrate-new:
	@read -p "Migration message: " msg && uv run alembic revision --autogenerate -m "$$msg"
