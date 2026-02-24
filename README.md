# Trump Tracking (Research MVP)

Evidence-first documentation system for Donald Trump public statements and related claims, designed for research, citation, and contradiction analysis.

## Goals
- Preserve high-signal statements with direct quotes and primary sources.
- Verify claims through a repeatable editorial workflow.
- Make entries searchable by date, topic, verdict, and impact.
- Support daily updates without sacrificing source quality.

## Scope
- Coverage window: June 16, 2015 to present.
- Subject: Donald Trump statements first; high-impact Trump-involved events second.
- Tone: factual, nonpartisan, and source-driven.

## Quick Start
```bash
cd /Users/jason/Documents/Trump_Tracking
python -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r requirements-dev.txt
python3 -m uvicorn backend.app.main:app --reload --reload-dir backend --reload-exclude ".venv/*"
```

Open `http://127.0.0.1:8000`.

If you prefer package mode, this also works after upgrading `pip`:
```bash
python3 -m pip install -e '.[dev]'
```

## Project Layout
- `backend/app/`: FastAPI app, models, and API routes.
- `backend/scripts/`: daily ingestion pipeline scaffolding.
- `agents/`: six role-specific AI agent playbooks and orchestration.
  - `agents/references/`: role knowledge and standards.
  - `agents/templates/`: structured handoff formats.
  - `agents/evals/`: role rubrics and test cases.
  - `agents/scorecards/`: weekly quality tracking.
- `docs/`: editorial policy, verification workflow, hosting/automation plan.
- `data/inbox/`: staged candidate entries for ingestion.
- `tests/`: API tests.

## API Endpoints
- `GET /api/claims/search`
- `GET /api/claims/{id}`
- `POST /api/claims`
- `GET /api/dashboard/summary`
- `GET /health`
- `GET /api/workflow/summary`
- `GET /api/workflow/queues/{stage}` where `stage` is `fact_check|editorial|verified|rejected`
- `POST /api/workflow/intake`
- `POST /api/workflow/fact-check/{claim_id}`
- `POST /api/workflow/editorial/{claim_id}`

## Hosting (POC)
- Recommended path: GitHub + Render (app) + Neon (Postgres).
- Deployment config: `render.yaml`
- Step-by-step setup: `docs/deploy_render_neon.md`

## Data Quality Rules
- Each claim must reference a primary source.
- Tier-based source policy governs corroboration requirements.
- Public list defaults to verified entries only.

## Pipeline Modes
- `current` mode: daily intake for current/future events, stricter validation and fast publish path.
- `backlog` mode: historical catch-up that can ingest intake records before full fact-check completion.

See:
- `docs/source_tier_policy.md`
- `docs/review_workflow.md`
- `docs/backfill_targets.md`
- `docs/automation_and_hosting.md`
- `docs/deploy_render_neon.md`
- `docs/AI_HANDOFF.md`
- `docs/agent_roles.md`
