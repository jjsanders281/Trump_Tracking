# DevOps Agent Reference

## Platform: Railway
- **Project:** trump-tracking (ID: `3fece4a3-6a7a-40ba-8b97-0f9ae1b5d853`)
- **App service:** trump-tracking-app (ID: `2f59e73d-d87e-4596-aa81-0a7941f38c45`)
- **Database service:** Postgres-p1K8 (ID: `050d5430-d628-420b-ade2-4d9140b1fcd7`)
- **App URL:** `https://trump-tracking-app-production.up.railway.app`
- **GitHub repo:** `jjsanders281/Trump_Tracking` (auto-deploy on push to `main`)

## CLI Commands

### Deployment
```bash
railway up --detach              # Manual deploy from local directory
railway service status           # Check build/deploy status
railway service logs             # View recent logs
railway down                     # Rollback to previous deployment
railway service redeploy         # Redeploy latest without code changes
```

### Environment Variables
```bash
railway variables --json                          # List all vars on linked service
railway variables set KEY=value KEY2=value2       # Set vars (triggers redeploy)
railway service link trump-tracking-app           # Switch to app service context
railway service link Postgres-p1K8                # Switch to DB service context
```

### Database Access
```bash
railway connect postgres         # Open psql shell to production DB
```

### Service Management
```bash
railway whoami                   # Verify auth
railway status                   # Project/service/environment info
railway open                     # Open Railway dashboard in browser
```

## Environment Variables (App Service)
| Variable | Value | Notes |
|----------|-------|-------|
| `DATABASE_URL` | `${{Postgres-p1K8.DATABASE_URL}}` | Railway reference variable, resolves to internal Postgres URL |
| `APP_ENV` | `production` | |
| `SEED_SAMPLE_DATA` | `false` | Set `true` only for initial seeding |
| `PORT` | `8000` | Railway routes external traffic to this port |

## Deployment Flow
1. Code pushed to `main` on GitHub.
2. Railway detects push, starts Nixpacks build.
3. Nixpacks detects `requirements.txt` + `Procfile`, installs deps, starts uvicorn.
4. Health check: Railway hits `GET /health` to confirm service is live.
5. Traffic switches to new deployment.
6. Previous deployment kept for instant rollback via `railway down`.

## Procfile
```
web: python -m uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

## Build Optimization
- Nixpacks caches pip installs between builds.
- Keep `requirements.txt` stable to maximize cache hits.
- Avoid adding large binary deps unless necessary.

## Rollback Procedure
1. Run `railway down` to remove latest deployment and restore previous.
2. Verify `GET /health` returns `{"status": "ok"}`.
3. If previous deployment is also broken, push a known-good commit to `main`.

## Monitoring Checklist
- `curl -s https://trump-tracking-app-production.up.railway.app/health` — should return `{"status": "ok"}`.
- `railway service logs` — scan for 5xx errors, connection failures, OOM kills.
- `railway service status` — confirm latest deployment is `SUCCESS`.

## Scheduled Tasks (Future)
- Daily ingestion pipeline: run `make ingest` via Railway cron job or GitHub Actions.
- Backlog processing: `make ingest-backlog` for historical batch ingestion.
- Health check pings: external uptime monitor hitting `/health` every 5 minutes.
