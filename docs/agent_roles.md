# Agent Role Map

## Why Role Separation
This project has competing priorities: speed, verification rigor, and usable presentation. Dedicated roles reduce mistakes and keep responsibilities auditable.

## Active 10-Agent Setup

### Editorial Pipeline
- Research Agent
  - File: `agents/research-agent.md`
  - Output: candidate statement packets with quote, timestamp, venue, and primary source.
- Fact-Check Agent
  - File: `agents/fact-check-agent.md`
  - Output: evidence memo, verdict proposal, and source tier notes.
- Editorial Agent
  - File: `agents/editorial-agent.md`
  - Output: approved neutral-language summary and final publish status.

### Technical Operations
- Backend Agent
  - File: `agents/backend-agent.md`
  - Output: API endpoints, business logic, Pydantic schemas, and passing tests.
- Frontend Agent
  - File: `agents/frontend-agent.md`
  - Output: HTML/CSS/JS UI features, responsive layouts, and accessible search/workflow views.
- Database Agent
  - File: `agents/database-agent.md`
  - Output: schema changes, migration scripts, query optimizations, and integrity audits.
- DevOps Agent
  - File: `agents/devops-agent.md`
  - Output: deployments, environment config, monitoring verification, and rollback actions.

### Cross-Cutting
- Design Agent
  - File: `agents/design-agent.md`
  - Output: UX improvements, visualization specs, and accessibility refinements.
- Implementation Agent
  - File: `agents/implementation-agent.md`
  - Output: API/data/frontend changes, tests, and deployment-safe changesets.
- Security & Reliability Agent
  - File: `agents/security-reliability-agent.md`
  - Output: hardening actions, monitoring, incident handling, and backup verification.

## Handoff Contract
Every handoff must include:
- Claim ID (or temporary intake ID) for editorial handoffs
- Source list with tiers
- Reviewer identity
- Timestamp of review decision
- Files changed and test results for technical handoffs

## Orchestration
- Execution order and escalation rules are defined in `agents/ORCHESTRATOR.md`.
- Expertise framework assets:
  - References: `agents/references/`
  - Output templates: `agents/templates/`
  - Role evaluations: `agents/evals/`
  - Weekly scorecards: `agents/scorecards/`

## Minimum Team for MVP
One person can perform all roles initially, but should still use role-specific checklists to preserve consistency and auditability.
