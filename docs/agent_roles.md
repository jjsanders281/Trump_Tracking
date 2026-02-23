# Agent Role Map

## Why Role Separation
This project has competing priorities: speed, verification rigor, and usable presentation. Dedicated roles reduce mistakes and keep responsibilities auditable.

## Roles and Deliverables
- Researcher agent
  - Output: candidate statement packets with quote, timestamp, venue, and primary source.
- Fact-checker agent
  - Output: evidence memo, verdict proposal, and source tier notes.
- Editor agent
  - Output: approved neutral-language summary and final publish status.
- Database agent
  - Output: normalized records, tags, contradiction links, and revision entries.
- Web agent
  - Output: searchable UI updates and dashboard visualizations.
- Automation agent
  - Output: scheduled pipeline runs, ingestion logs, and alerting.

## Handoff Contract
Every handoff must include:
- Claim ID (or temporary intake ID)
- Source list with tiers
- Reviewer identity
- Timestamp of review decision

## Minimum Team for MVP
One person can perform all roles initially, but still use the same handoff checklist and logs to preserve consistency.
