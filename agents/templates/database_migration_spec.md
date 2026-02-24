# Database Migration Spec

## Summary
Brief description of schema change and why it is needed.

## Changes
| Action | Table | Column/Constraint | Type | Default | Notes |
|--------|-------|-------------------|------|---------|-------|
| ADD/ALTER/DROP | | | | | |

## Forward Migration SQL
```sql
-- Postgres-compatible DDL
```

## Rollback SQL
```sql
-- Exact reversal of forward migration
```

## SQLAlchemy Model Changes
Files and lines affected in `backend/app/models.py`.

## Data Impact
- Rows affected:
- Backfill needed (Y/N):
- Backfill query:

## Testing
- [ ] Tested on local SQLite
- [ ] Tested on Postgres (Railway or local)
- [ ] Existing tests still pass (`make test`)
- [ ] Data integrity check run after migration

## Deployment Coordination
Describe timing: can this run while the app is live, or does it need a maintenance window?
