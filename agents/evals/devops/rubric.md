# DevOps Agent Evaluation Rubric

Score each criterion 0-2. Target average: ≥ 1.7.

## Criteria

### 1. Deployment Success
- 0: Deployment failed or caused downtime.
- 1: Deployment succeeded but required manual intervention.
- 2: Deployment succeeded cleanly with health check verified automatically.

### 2. Rollback Readiness
- 0: No rollback plan or broken rollback path.
- 1: Rollback possible but requires manual steps beyond `railway down`.
- 2: Instant rollback available via `railway down`, tested and verified.

### 3. Environment Hygiene
- 0: Secrets exposed in logs, commits, or echoed to terminal.
- 1: Secrets protected but environment variables inconsistent or undocumented.
- 2: All env vars documented, secrets managed via Railway platform only, no leakage.

### 4. Monitoring Coverage
- 0: No health check verification after deployment.
- 1: Manual health check but no log review.
- 2: Health check verified, service logs reviewed for errors, build status confirmed.

### 5. Pipeline Reliability
- 0: Auto-deploy pipeline disconnected or misconfigured.
- 1: Pipeline works but build failures not detected promptly.
- 2: Pipeline connected, builds monitored, failures detected and communicated immediately.
