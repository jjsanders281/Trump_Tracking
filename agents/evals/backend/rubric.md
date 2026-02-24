# Backend Agent Evaluation Rubric

Score each criterion 0-2. Target average: ≥ 1.7.

## Criteria

### 1. Correctness
- 0: Endpoint returns wrong data or crashes.
- 1: Endpoint works but edge cases cause errors (empty results, missing relations).
- 2: Endpoint handles all expected inputs and edge cases correctly.

### 2. Postgres Compatibility
- 0: Query uses patterns that fail on Postgres (DISTINCT+ORDER BY without subquery).
- 1: Query works on Postgres but uses suboptimal patterns.
- 2: Query uses documented subquery pattern, tested against both SQLite and Postgres.

### 3. Test Coverage
- 0: No tests for new or changed endpoints.
- 1: Happy-path test exists but edge cases untested.
- 2: Tests cover happy path, error cases, and boundary conditions.

### 4. Type Safety and Schema Compliance
- 0: Missing type hints or Pydantic schemas.
- 1: Type hints present but incomplete or schemas missing validation.
- 2: Full type hints, Pydantic v2 schemas with proper validation, `model_validate` used.

### 5. Audit Trail
- 0: State changes made without `_record_revision()` calls.
- 1: Revision recorded but summary is vague or missing actor identity.
- 2: Every state change recorded with entity type, ID, actor, and descriptive summary.
