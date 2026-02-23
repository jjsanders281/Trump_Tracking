# Verification Workflow

## Publication Rule
Public index shows verified entries only.

## Statuses
- `pending`: candidate claim exists but has not passed review.
- `verified`: two-person review complete and publishable.
- `rejected`: insufficient evidence or out-of-scope.

## Daily Process
1. Research ingest: collect candidate statements with quote + source links.
2. Claim extraction: split into atomic claims.
3. Evidence collection: attach primary source and corroboration.
4. Fact-check assessment: assign verdict with written rationale.
5. Editorial pass: second reviewer confirms evidence chain and wording.
6. Publish: entry becomes searchable in public index.

## Required Fields Before Verification
- Exact quote text.
- Event datetime and venue.
- Primary source URL.
- Topic and tags.
- Verdict rationale.
- Reviewer identities (`reviewer_primary`, `reviewer_secondary`).

## Corrections
- Never overwrite silently.
- Record edits in `revisions` with timestamp and reason.
- If verdict changes, preserve prior verdict in history.
