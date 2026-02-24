# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make dev          # Run FastAPI dev server with hot reload
make test         # Run pytest suite
make lint         # Run ruff check
make format       # Run ruff format
make seed         # Seed demo data into local SQLite
make ingest       # Run current-events pipeline for today's date
make ingest-backlog  # Run historical backlog pipeline batch

# Run a single test
python -m pytest tests/test_api.py::test_health -v

# Deploy to Railway (auto-deploy on push to main is also configured)
railway up --detach
```

## Architecture

FastAPI monolith serving both a JSON API and a vanilla HTML/CSS/JS frontend from static files. SQLAlchemy ORM with PostgreSQL in production (Railway), SQLite for local dev.

**Core data flow:** Statements → Claims → Assessments + Sources + Tags

- A **Statement** is a raw quote/event with timestamp, venue, speaker, impact score (1-5)
- A **Claim** is an atomic assertion extracted from a statement, assigned a topic
- An **Assessment** attaches a verdict (`true|mixed|misleading|false|unverified|unfulfilled|contradicted`) and publication status (`pending|verified|rejected`)
- **Sources** provide evidence with tier ratings (1=primary wire/official, 2=major outlet, 3=partisan/context-only)
- **Contradictions** link conflicting claims directionally
- **Revisions** provide audit trail for all entity changes

Only claims with `publish_status="verified"` appear in the default public API response.

**Ingestion pipeline** (`backend/scripts/daily_pipeline.py`) supports two modes:
- `current`: reads `data/inbox/current/YYYY-MM-DD.jsonl` (or legacy root date file), strict validation for rapid daily operations.
- `backlog`: reads `data/inbox/backlog/*.jsonl`, allows intake-first historical catch-up before final verification.

**Workflow states** (derived from latest assessment):
- `fact_check`: intake exists but no finalized assessment yet.
- `editorial`: latest assessment is `pending` and ready for second review.
- `verified`: latest assessment approved for publication.
- `rejected`: latest assessment rejected.

## Agent Playbooks (6 Roles)

Role playbooks are stored in `agents/`:
- `ORCHESTRATOR.md`
- `research-agent.md`
- `fact-check-agent.md`
- `editorial-agent.md`
- `design-agent.md`
- `implementation-agent.md`
- `security-reliability-agent.md`

Role summary and handoff contract are also documented in `docs/agent_roles.md`.

Expert-calibration assets:
- `agents/references/`
- `agents/templates/`
- `agents/evals/`
- `agents/scorecards/`

## Key Gotchas

**Postgres DISTINCT+ORDER BY:** SQLite is lenient but Postgres requires ORDER BY columns in the SELECT DISTINCT list. The `search_claims()` function in `crud.py` uses a subquery pattern: first fetches distinct claim IDs with ordering columns, then loads full objects by ID. Do not revert to a simple `.distinct().order_by()` chain.

**Database URL normalization:** `db.py` converts `postgres://` and `postgresql://` URLs to `postgresql+psycopg://` for psycopg3 driver compatibility. This runs automatically on startup.

**Eager loading everywhere:** All read paths use `selectinload` for relationships. Follow this pattern to avoid N+1 queries.

**Tag handling:** Tags are case-insensitive, auto-lowercased, and auto-created on insertion via `_get_or_create_tags()`.

## Hosting

- **Platform:** Railway (app + PostgreSQL in one project)
- **App URL:** https://trump-tracking-app-production.up.railway.app
- **GitHub auto-deploy:** Pushes to `main` on `jjsanders281/Trump_Tracking` trigger Railway builds
- **Environment variables:** `DATABASE_URL` (references Postgres internal URL), `APP_ENV=production`, `SEED_SAMPLE_DATA=false`, `PORT=8000`
- **Health check:** `GET /health` → `{"status": "ok"}`

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Frontend UI |
| GET | `/health` | Health check |
| GET | `/api/claims/search` | Filtered search (params: `q`, `topic`, `verdict`, `start_date`, `end_date`, `min_impact`, `verified_only`, `limit`, `offset`) |
| GET | `/api/claims/{id}` | Single claim with all relationships |
| POST | `/api/claims` | Create claim bundle (statement + claim + sources + assessment) |
| GET | `/api/dashboard/summary` | Verdict/topic breakdowns, totals |
| GET | `/api/workflow/summary` | Queue counts by workflow stage |
| GET | `/api/workflow/queues/{stage}` | Queue items (`fact_check`, `editorial`, `verified`, `rejected`) |
| POST | `/api/workflow/intake` | Research intake creation (no assessment required) |
| POST | `/api/workflow/fact-check/{id}` | Submit/update pending fact-check assessment |
| POST | `/api/workflow/editorial/{id}` | Apply editorial verification/rejection decision |
| PATCH | `/api/claims/{id}` | Partial update claim/statement fields (body: `ClaimPatchPayload`) |
| PUT | `/api/claims/{id}/sources` | Replace all sources on a claim (body: `SourcesReplacePayload`) |
| POST | `/api/workflow/reopen/{id}` | Reopen a verified/rejected claim for re-review |
| DELETE | `/api/claims/{id}` | Delete claim and all related records |

## Code Style

- Ruff for linting and formatting, line-length=100, target Python 3.9
- Type hints on all function signatures (`from __future__ import annotations`)
- Pydantic v2 schemas with `model_validate` for ORM→schema conversion
