# Database Agent Reference

## Schema Overview (8 Tables)

### Core Tables
- **statements**: raw quote/event. Key fields: `occurred_at`, `speaker`, `venue`, `quote`, `context`, `primary_source_url`, `impact_score` (CHECK 1-5).
- **claims**: atomic assertion. FK to `statement_id`. Key fields: `claim_text`, `topic`, `claim_kind`.
- **assessments**: verdict + review metadata. FK to `claim_id`. Key fields: `verdict` (CHECK enum), `rationale`, `publish_status` (CHECK pending/verified/rejected), `verified_at`.
- **sources**: evidence links. FK to `claim_id`. Key fields: `publisher`, `url`, `source_tier` (CHECK 1-3), `is_primary`.

### Supporting Tables
- **tags**: named labels, `name` UNIQUE. Many-to-many with claims via **claim_tags** junction table.
- **contradictions**: directional links between conflicting claims. UNIQUE constraint on `(claim_id, contradicts_claim_id)`.
- **revisions**: audit log. Fields: `entity_type`, `entity_id`, `changed_by`, `change_summary`, `changed_at`.

## Indexes
Indexed columns: `statements.occurred_at`, `.speaker`, `.region`; `claims.statement_id`, `.topic`, `.claim_kind`; `assessments.claim_id`, `.verdict`, `.publish_status`; `sources.claim_id`, `.publisher`, `.source_tier`; `tags.name`; `contradictions.claim_id`, `.contradicts_claim_id`; `revisions.entity_type`, `.entity_id`.

## Constraint Rules
- `impact_score` must be 1-5 (CheckConstraint).
- `verdict` must be one of: true, mixed, misleading, false, unverified, unfulfilled, contradicted.
- `publish_status` must be one of: pending, verified, rejected.
- `source_tier` must be 1-3.
- Contradiction pairs are unique (no duplicate directional links).

## Connection Configuration
- **Local dev**: `sqlite:///./tracker.db` (default when `DATABASE_URL` not set).
- **Production**: PostgreSQL on Railway, internal URL via `DATABASE_URL` env var.
- URL normalization in `db.py`: `postgres://` or `postgresql://` → `postgresql+psycopg://`.
- Pool settings for managed Postgres: `pool_pre_ping=True`, `pool_recycle=1800`.
- SQLite requires `check_same_thread=False`.

## Migration Strategy (Pre-Alembic)
Currently using `Base.metadata.create_all()` on startup. This only creates missing tables — it does not alter existing ones.

**For schema changes on production:**
1. Write the ALTER TABLE SQL.
2. Test locally against SQLite.
3. Connect to Railway Postgres via `railway connect postgres` and execute manually.
4. Update SQLAlchemy models to match.
5. Document rollback DDL.

**Alembic adoption planned:** when schema changes become frequent, introduce Alembic with `autogenerate` for migration scripts.

## Data Integrity Checks
- Orphaned claims (no statement): `SELECT id FROM claims WHERE statement_id NOT IN (SELECT id FROM statements)`
- Orphaned assessments: `SELECT id FROM assessments WHERE claim_id NOT IN (SELECT id FROM claims)`
- Contradictions referencing deleted claims: check both `claim_id` and `contradicts_claim_id`.
- Claims with no sources: valid for intake-only, but should not reach `verified` status.

## Backup and Recovery
- Railway Postgres includes automated backups.
- For manual backup: `railway connect postgres` then `pg_dump`.
- For restore: `psql` into Railway Postgres with dump file.
- Always test restore on a separate database before applying to production.
