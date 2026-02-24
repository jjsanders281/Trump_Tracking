# Deploying Changes to Production

This guide explains how to publish local changes to the live site at:
**https://trump-tracking-app-production.up.railway.app**

## How Deployment Works

The app runs on **Railway**. There are two ways to deploy:

1. **Git push to `main`** (preferred) — Railway auto-deploys on every push to the `main` branch.
2. **Railway CLI** — Pushes directly from the working directory without a git commit.

---

## Method 1: Git Push (Preferred)

This is the standard workflow. Railway watches the GitHub repo and auto-deploys.

```bash
# 1. If frontend files changed, bump static asset version to bust browser cache
make bust-assets

# 2. Stage changed files (be specific, don't use git add -A)
git add backend/app/static/styles.css backend/app/static/app.js backend/app/static/index.html

# 3. Commit with a descriptive message
git commit -m "Improve dashboard interactivity and review queue UX"

# 4. Push to main — Railway auto-deploys on push
git push origin main
```

After pushing, Railway will:
- Detect the change (usually within 10-30 seconds)
- Install dependencies from `requirements.txt`
- Start the app using the `Procfile`
- The new version goes live in ~1-2 minutes

### Verify the deploy
```bash
# Check the health endpoint
curl https://trump-tracking-app-production.up.railway.app/health
# Should return: {"status": "ok"}
```

---

## Method 2: Railway CLI (Direct Push)

Use this when you want to deploy without committing to git (e.g., testing something on prod).

```bash
# From the project root:
railway up --detach
```

This uploads the current working directory to Railway and deploys it. The `--detach` flag returns immediately without streaming logs.

### Prerequisites for CLI deploy
- Railway CLI installed: `npm install -g @railway/cli`
- Authenticated: `railway login` (already done as jason.sanders@mac.com)
- Linked to project: should already be linked to `trump-tracking`

---

## Pre-Deploy Checklist

Before deploying, always run:

```bash
# Run linter (must pass clean)
make lint

# Run tests (must all pass)
make test

# If frontend changed, bust static asset cache key in index.html
make bust-assets

# Optionally start the dev server and verify locally
make dev
# Then visit http://localhost:8000 and check your changes
```

---

## What Gets Deployed

Railway uses **Nixpacks** auto-detection with the `Procfile`:
```
web: python -m uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

The static frontend files (`backend/app/static/`) are served directly by FastAPI — there is no separate build step for the frontend. Any changes to `styles.css`, `app.js`, or `index.html` go live as soon as the deploy finishes.

---

## Environment Variables (Already Configured)

These are set in Railway and do not need to be changed for normal deploys:

| Variable | Value | Notes |
|----------|-------|-------|
| `DATABASE_URL` | (Railway internal ref) | Points to the Postgres service |
| `APP_ENV` | `production` | Enables production behaviors |
| `SEED_SAMPLE_DATA` | `false` | Set to `true` only for initial demo data |
| `PORT` | `8000` | Railway sets this automatically |

---

## Troubleshooting

### Deploy didn't trigger after git push
- Confirm you pushed to `main`: `git log --oneline origin/main -3`
- Check Railway dashboard for build status
- Auto-deploy may be paused — check Railway project settings

### Site shows old version after deploy
- Confirm cache-busting query param is present in HTML:
  - `curl -s https://trump-tracking-app-production.up.railway.app/ | rg "styles.css\\?v=|app.js\\?v="`
- If missing, rerun `make bust-assets`, commit, and push.
- Hard-refresh the browser: `Ctrl+Shift+R` / `Cmd+Shift+R`

### Railway CLI errors
```bash
# Re-authenticate if token expired
railway login

# Verify you're linked to the right project
railway status
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Deploy via git | `git push origin main` |
| Deploy via CLI | `railway up --detach` |
| Bump static cache key | `make bust-assets` |
| Full deploy prep | `make deploy-prep` |
| Check prod health | `curl https://trump-tracking-app-production.up.railway.app/health` |
| View prod logs | `railway logs` |
| Run tests first | `make test` |
| Run linter first | `make lint` |
| Local dev server | `make dev` |
