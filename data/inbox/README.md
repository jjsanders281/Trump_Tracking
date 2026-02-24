# Inbox Format

The pipeline supports two ingestion modes:
- Current pipeline (daily): `data/inbox/current/YYYY-MM-DD.jsonl`
- Backlog pipeline (historical): `data/inbox/backlog/*.jsonl`

Backward compatibility:
- `data/inbox/YYYY-MM-DD.jsonl` is still read by current mode if present.

Required keys:
- `occurred_at` (ISO datetime)
- `quote`
- `venue`
- `primary_source_url`
- `claim_text`
- `topic`
- `sources` (array, required for `current` mode)
- `assessment` (object, optional in `backlog` mode)

Example line:
```json
{"occurred_at":"2026-02-23T13:00:00","quote":"...","venue":"Interview","primary_source_url":"https://...","claim_text":"...","topic":"Healthcare","impact_score":4,"sources":[{"publisher":"AP","url":"https://...","source_tier":1,"is_primary":false}],"assessment":{"verdict":"false","rationale":"...","reviewer_primary":"researcher_1","reviewer_secondary":"editor_1","source_tier_used":1,"publish_status":"verified","verified_at":"2026-02-23T16:00:00"}}
```

Run examples:
```bash
# Current daily file
python backend/scripts/daily_pipeline.py --mode current --date 2026-02-23

# Backlog catch-up from all backlog files
python backend/scripts/daily_pipeline.py --mode backlog --max-items 500
```
