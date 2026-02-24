# Multi-Agent Orchestrator (10 Roles)

Use these ten agents together to run the site reliably and at scale.

## Agent Groups

### Editorial Pipeline (content flow)
1. `research-agent.md` — collect candidate statements
2. `fact-check-agent.md` — validate evidence, assign verdicts
3. `editorial-agent.md` — approve language, publish decisions

### Technical Operations (system flow)
4. `backend-agent.md` — API routes, business logic, schemas
5. `frontend-agent.md` — browser UI, search, dashboards, workflow panels
6. `database-agent.md` — schema, migrations, query performance, data integrity
7. `devops-agent.md` — deployment, CI/CD, environment config, monitoring

### Cross-Cutting
8. `design-agent.md` — UX specs, visualizations, accessibility
9. `implementation-agent.md` — feature coordination across backend/frontend/database
10. `security-reliability-agent.md` — secrets, uptime, incidents, backups

## Daily Operating Cycle

### Editorial Track
1. Research collects candidate statements with primary sources.
2. Fact-check validates evidence and proposes verdicts.
3. Editorial approves language and publish status.

### Technical Track (parallel with editorial)
4. Backend implements new API endpoints and business logic.
5. Frontend builds UI features for new data and workflows.
6. Database manages schema changes and query optimization.
7. DevOps deploys changes and verifies production health.

### Review Track
8. Design updates visual summaries and filter UX.
9. Implementation coordinates cross-cutting feature work.
10. Security/Reliability reviews logs, backups, and incidents.

Use role references in `agents/references/` and enforce schema outputs from `agents/templates/`.

## Required Handoff Payload

### Editorial Handoffs
Every editorial handoff must include:
- `claim_id` (or `intake_id` before insertion)
- `statement_date` and `statement_source_url`
- `topic`, `claim_kind`, and `impact_score`
- source list with tiers
- reviewer identity + decision timestamp
- open risks or unresolved questions

### Technical Handoffs
Every technical handoff must include:
- Files changed and summary of changes
- Test results (`make test` output)
- Lint results (`make lint` output)
- Deployment verification (health check, log review)
- Rollback plan for schema or infrastructure changes

## Escalation Rules
- Missing primary source: block publication.
- Source conflict unresolved: mark `pending` and escalate to Editorial.
- Security incident or suspected abuse: escalate immediately to Security/Reliability.
- Production outage or schema break: DevOps + Security/Reliability joint incident response.
- Schema migration failure: Database + DevOps joint rollback.
- API regression (tests fail): Backend blocks deployment until fixed.
- Frontend XSS or injection risk: Frontend + Security/Reliability joint review.

## Shared Success Metrics
- Verification turnaround time
- Percentage of entries with full source trail
- Search accuracy and discovery success
- Uptime and mean time to recovery (MTTR)
- Correction rate and correction response time
- Deployment success rate
- API latency (p95 < 500ms search, < 300ms dashboard)
- Test pass rate (100% target)

## Calibration Loop
1. Run role eval scenarios from `agents/evals/`.
2. Score with role rubrics.
3. Log weekly metrics in `agents/scorecards/weekly-template.md`.
4. Update references/templates for repeated failure modes.
