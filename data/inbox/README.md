# Inbox Format

Daily pipeline input files live here as `YYYY-MM-DD.jsonl`.
Each line is one verified candidate entry in JSON form.

Required keys:
- `occurred_at` (ISO datetime)
- `quote`
- `venue`
- `primary_source_url`
- `claim_text`
- `topic`
- `sources` (array)
- `assessment` (object, `publish_status` must be `verified`)

Example line:
```json
{"occurred_at":"2026-02-23T13:00:00","quote":"...","venue":"Interview","primary_source_url":"https://...","claim_text":"...","topic":"Healthcare","impact_score":4,"sources":[{"publisher":"AP","url":"https://...","source_tier":1,"is_primary":false}],"assessment":{"verdict":"false","rationale":"...","reviewer_primary":"researcher_1","reviewer_secondary":"editor_1","source_tier_used":1,"publish_status":"verified","verified_at":"2026-02-23T16:00:00"}}
```
