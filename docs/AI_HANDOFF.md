# AI Handoff (POC Snapshot)

Last updated: February 23, 2026
Repository: https://github.com/jjsanders281/Trump_Tracking

## 1) Project Intent (Decisions Already Made)
- Build a factual, research-style tracker focused on Donald Trump statements (quote-first).
- Coverage window: June 16, 2015 to present.
- Tone: neutral/nonpartisan language.
- Publication rule: verified entries only.
- Include contradiction linking where later claims conflict with earlier claims.
- Add impact scoring (1-5) and strong filtering/search.
- Hosting target: GitHub + Render (web app) + Neon (Postgres).

## 2) What Is Already Implemented
- FastAPI app + static UI with search filters and claim detail panel.
- SQLAlchemy schema for statements, claims, assessments, sources, tags, contradictions, revisions.
- Verification-oriented data model and docs.
- Daily ingestion pipeline scaffold with role-based stages (research/fact-check/database).
- Render deployment blueprint (`render.yaml`).
- Neon URL normalization in DB layer (`postgres://` and `postgresql://` handling).
- Local tests and linting are passing.

## 3) Key Files
- App entry: `backend/app/main.py`
- DB models: `backend/app/models.py`
- DB config: `backend/app/db.py`
- Search/business logic: `backend/app/crud.py`
- Frontend UI: `backend/app/static/index.html`, `app.js`, `styles.css`
- Ingestion pipeline: `backend/scripts/daily_pipeline.py`
- Deploy guide: `docs/deploy_render_neon.md`
- Source policy: `docs/source_tier_policy.md`
- Review workflow: `docs/review_workflow.md`

## 4) Current Deployment Status
- GitHub repo exists and has been pushed.
- Render service + Neon DB are NOT fully completed yet.
- User requested support for this setup and may need step-by-step guidance in dashboard UI.

## 5) Security Note
- A Neon connection string was pasted in chat and should be treated as exposed.
- Action required: rotate/recreate Neon credentials before using in production env vars.

## 6) Local Runbook (Works)
```bash
cd /Users/jason/Documents/Trump_Tracking
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r requirements-dev.txt
python3 -m uvicorn backend.app.main:app --reload --reload-dir backend --reload-exclude ".venv/*"
```

## 7) Verified Checks
- `python3 -m ruff check .` passed.
- `python3 -m pytest -q` passed (3 tests).

## 8) Recommended Next Actions (Priority)
1. Complete Neon setup and rotate credentials.
2. Configure Render environment variables (`DATABASE_URL`, `APP_ENV=production`, `SEED_SAMPLE_DATA=false`).
3. Deploy and verify `/health`, `/api/dashboard/summary`, `/`.
4. Add admin/reviewer UI for approve/reject workflow (current ingestion is JSONL-driven).
5. Add first real visualizations (verdict distribution, timeline, contradiction list).
6. Wire scheduled ingest to production DB via GitHub Actions secrets.

## 9) Constraints / Known Friction
- Tool session could not use user's macOS keychain-backed GitHub auth directly.
- User prefers high guidance and low operational complexity.
- Project is POC; low traffic expected.

## 10) Suggested Alternate Second Opinion Focus
If another AI takes over, ask it to evaluate:
- Whether to keep static frontend served by FastAPI vs split frontend.
- Whether to introduce Alembic now (recommended before production schema changes).
- Whether to add a moderation queue table for pending claims instead of JSONL-only intake.
