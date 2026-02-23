# Repository Guidelines

## Project Structure & Module Organization
Keep the repository root minimal and organized by purpose:
- `src/` for application code, grouped by domain (for example: `src/collect/`, `src/normalize/`, `src/reporting/`).
- `tests/` mirroring `src/` paths (for example: `tests/collect/test_fetch_events.py`).
- `data/` for small, non-sensitive fixtures only.
- `scripts/` for one-off maintenance or import tasks.
- `docs/` for architecture notes and process docs.

Place shared interfaces in `src/core/` and keep external API/database logic in boundary modules such as `src/adapters/`.

## Build, Test, and Development Commands
This project is newly bootstrapped; use these standard commands when adding code:
- `python -m venv .venv && source .venv/bin/activate`: create and activate local environment.
- `pip install -r requirements-dev.txt`: install runtime and developer dependencies.
- `pytest`: run the full test suite.
- `ruff check .`: run lint checks.
- `ruff format .`: apply formatting.
- `python -m src`: run the application entry point (after `src/__main__.py` exists).

If tooling changes, update this file and `README.md` in the same PR.

## Coding Style & Naming Conventions
Use Python 3.9+ with 4-space indentation and explicit type hints for public functions.
- Modules/functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`

Prefer small, testable functions. Keep I/O at module boundaries and keep domain logic pure where possible.

## Testing Guidelines
Use `pytest` with files named `test_*.py` and descriptive test names such as `test_fetch_events_retries_on_429`.
Add unit tests for new logic and regression tests for bug fixes. Target at least 85% line coverage on changed modules.

## Commit & Pull Request Guidelines
No established git history exists yet; adopt Conventional Commits:
- `feat: add election filing ingest client`
- `fix: guard against empty response payload`

PRs should include:
- A short summary of behavior changes
- Linked issue/ticket (if available)
- Test evidence (commands run and results)
- Example output or screenshots for reporting/UI changes

Keep PRs focused and reviewable; split broad work into smaller, sequential PRs.
