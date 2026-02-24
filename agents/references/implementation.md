# Implementation Reference

## Engineering Priorities
- Preserve data integrity in claim bundle insertions.
- Keep search behavior consistent across SQLite and Postgres.
- Add tests for every bug fix and schema-affecting change.

## Release Guardrails
- Lint and tests must pass before release.
- Validate any query changes against Postgres behavior.
- For schema changes, provide migration and rollback steps.

## Performance Targets (POC)
- Search endpoint p95 under 500ms on moderate dataset.
- Dashboard summary endpoint p95 under 300ms.
