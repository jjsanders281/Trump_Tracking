# Automation and Hosting Plan

## Automation Architecture
Use a daily pipeline with role-specific stages:
1. Research agent: gathers candidate statements from approved sources.
2. Fact-check agent: validates evidence requirements and draft verdict.
3. Editorial agent: confirms wording and publish status.
4. Database agent: writes verified entries to production DB.
5. Web agent: rebuilds cache/index and publishes updates.

Current implementation scaffold:
- Script: `backend/scripts/daily_pipeline.py`
- Input queue: `data/inbox/YYYY-MM-DD.jsonl`
- Rule: only `publish_status = verified` entries are inserted.

## Hosting Recommendation
- App: FastAPI service on Render.
- Database: managed Postgres on Neon.
- Static assets: served by FastAPI for MVP; split CDN later if needed.

## Deployment Pattern
- `main` branch deploys automatically.
- Managed Postgres URL provided through `DATABASE_URL` secret.
- Daily cron triggers ingestion in dry-run first, then live after review.

See `docs/deploy_render_neon.md` for setup steps.

## Reliability Controls
- Keep append-only revision logs.
- Add daily DB backup and weekly offsite export.
- Require audit fields for all verdict changes.
