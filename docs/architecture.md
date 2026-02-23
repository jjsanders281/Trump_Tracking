# Architecture Overview

## Components
- API: FastAPI app (`backend/app/main.py`)
- Storage: SQLAlchemy models with SQLite local / Postgres production
- UI: static HTML + JS served from `/static`
- Pipeline: JSONL inbox to verified DB inserts (`backend/scripts/daily_pipeline.py`)

## Data Flow
1. Candidate records enter `data/inbox`.
2. Pipeline validates mandatory evidence fields.
3. Verified records are inserted into normalized tables.
4. UI queries search endpoint and renders filtered results.

## Search
Current MVP supports:
- keyword search across claim and quote text
- date range filters
- topic filter
- verdict filter
- minimum impact score filter
