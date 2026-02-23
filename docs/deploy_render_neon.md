# Deploying to Render + Neon (POC)

## Why this stack
- Render runs your FastAPI app continuously without your laptop.
- Neon provides managed Postgres, so data is durable and separate from app hosting.
- This project already supports Neon URLs through `DATABASE_URL`.

## Quick Overview
- Render hosts the API/UI process.
- Neon hosts the Postgres database.
- GitHub is the deployment source of truth.

## Step 1: Push to GitHub
```bash
cd /Users/jason/Documents/Trump_Tracking
git init
git add .
git commit -m "chore: initial trump-tracking mvp"
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```

## Step 2: Create Neon database
1. Sign in at Neon and create a project.
2. Create a database (for example: `trump_tracking`).
3. Copy the connection string from Neon dashboard.
4. Keep this string private; it will be your `DATABASE_URL` in Render.

## Step 3: Create Render web service
1. In Render, create a new Web Service from your GitHub repo.
2. Render can auto-detect `render.yaml`, or you can configure manually.
3. Set these environment variables:
- `DATABASE_URL=<your_neon_connection_string>`
- `SEED_SAMPLE_DATA=false`
- `APP_ENV=production`
4. Deploy.

## Step 4: Verify deployment
- Open `/health` and confirm `{"status": "ok"}`.
- Open `/api/dashboard/summary` and confirm JSON response.
- Open root `/` and confirm the UI loads.

## Notes for POC
- Render Free web services can spin down after inactivity.
- Neon free plans are sufficient for early POC testing.
- For production reliability, move to paid plans and add backups/alerts.

## Source links (checked February 23, 2026)
- Render FastAPI deploy guide: https://render.com/docs/deploy-fastapi
- Render free instances: https://render.com/docs/free
- Render pricing: https://render.com/pricing
- Neon pricing: https://neon.com/pricing
