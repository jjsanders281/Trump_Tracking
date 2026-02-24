# Backend Agent Reference

## Stack
- FastAPI 0.116+ with Pydantic v2 for request/response validation.
- SQLAlchemy 2.0 ORM with psycopg3 driver.
- Uvicorn ASGI server.
- Python 3.9+ target, ruff for lint/format (line-length=100).

## Code Conventions
- `from __future__ import annotations` at top of every file.
- Type hints on all function signatures.
- Pydantic `model_validate` for ORM→schema conversion (never manual dict construction).
- `selectinload` on every read path to prevent N+1 queries.

## Query Patterns

### The Postgres DISTINCT+ORDER BY Rule
SQLite is lenient, Postgres is not. When a query uses both `.distinct()` and `.order_by()`, the ORDER BY columns must appear in the SELECT list.

**Correct pattern (used in `search_claims` and `workflow_queue`):**
1. Build a subquery with `.with_entities(Claim.id, Statement.occurred_at).distinct()`
2. Apply `.order_by()`, `.offset()`, `.limit()` to the subquery.
3. Collect ordered IDs.
4. Fetch full objects with `_claim_query_with_relations(db).filter(Claim.id.in_(ids))`.
5. Re-sort in Python by the ID order.

**Never do:** `.distinct().order_by(Statement.occurred_at.desc())` directly on a query selecting full Claim objects.

### Eager Loading Helper
Use `_claim_query_with_relations(db)` for any query that returns Claim objects. This loads statement, assessments, sources, and tags in batch.

## Workflow State Machine
```
intake (no assessment) → fact_check
fact_check (pending, no reviewer) → editorial (pending, has reviewer)
editorial → verified | rejected
```

- `submit_fact_check`: creates or updates a pending assessment, adds sources and contradictions.
- `submit_editorial_decision`: promotes pending → verified or rejected, sets `verified_at`.
- Finalized claims (verified/rejected) block new fact-check submissions unless reopened.

## Ingestion Pipeline Modes
- `current`: reads `data/inbox/current/YYYY-MM-DD.jsonl`, strict validation.
- `backlog`: reads `data/inbox/backlog/*.jsonl`, intake-first (assessment optional).

## Revision Audit Trail
Every state change must call `_record_revision()` with entity type, ID, actor, and summary. This is not optional — it is required for editorial auditability.

## Test Conventions
- Tests in `tests/test_api.py` using `httpx.AsyncClient` or `TestClient`.
- Test database: separate SQLite file, cleaned up in `teardown_module()`.
- `SEED_SAMPLE_DATA=true` for test runs to populate demo data.
- Run: `make test` or `python -m pytest tests/test_api.py::test_name -v`.

## Error Handling
- `ValueError` in crud functions → caught in route handlers → `HTTPException` with 400 or 404.
- "not found" in error message → 404, everything else → 400.
