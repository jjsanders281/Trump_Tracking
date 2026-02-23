.PHONY: dev test lint format seed ingest

dev:
	python3 -m uvicorn backend.app.main:app --reload --reload-dir backend --reload-exclude ".venv/*"

test:
	python3 -m pytest

lint:
	python3 -m ruff check .

format:
	python3 -m ruff format .

seed:
	python -m backend.app.seed

ingest:
	python backend/scripts/daily_pipeline.py --date $$(date +%F)
