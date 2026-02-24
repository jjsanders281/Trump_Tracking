# Database Agent Evaluation Rubric

Score each criterion 0-2. Target average: ≥ 1.7.

## Criteria

### 1. Schema Integrity
- 0: Schema change violates constraints or breaks existing data.
- 1: Schema change is valid but missing constraints or indexes.
- 2: Schema change includes proper constraints, indexes, and maintains referential integrity.

### 2. Migration Safety
- 0: No rollback plan provided for schema change.
- 1: Rollback plan exists but untested.
- 2: Rollback plan documented, tested, and executable in production.

### 3. Cross-Database Compatibility
- 0: Change works on SQLite but fails on Postgres (or vice versa).
- 1: Change works on both but relies on database-specific behavior.
- 2: Change uses portable SQLAlchemy patterns that work identically on SQLite and Postgres.

### 4. Query Performance
- 0: New query causes visible latency increase or missing indexes on filtered columns.
- 1: Query performs adequately but lacks index analysis.
- 2: Query analyzed for performance, appropriate indexes added, eager loading used.

### 5. Data Integrity Validation
- 0: No verification that existing data remains consistent after change.
- 1: Spot-checked but no systematic validation.
- 2: Integrity check queries run before and after change, results documented.
