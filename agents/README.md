# Agent Expertise Framework

This folder turns role prompts into repeatable expert workflows.

## Structure
- `references/`: domain rules and role-specific playbooks.
- `templates/`: strict output schemas for handoffs.
- `evals/`: role rubrics and test cases.
- `scorecards/`: weekly tracking for quality trends.

## Operating Model
1. Run role work using the role file in `agents/*.md`.
2. Use the matching `templates/*` file for outputs.
3. Grade outputs against `evals/<role>/rubric.md`.
4. Log results in `scorecards/weekly-template.md`.
5. Update references and templates when error patterns repeat.

## Definition of "Expert"
A role is considered expert when it is:
- Consistent: passes rubric checks repeatedly.
- Defensible: every conclusion maps to evidence.
- Efficient: meets turnaround targets without quality drops.
- Auditable: handoff payloads are complete and structured.
