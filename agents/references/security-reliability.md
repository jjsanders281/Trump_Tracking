# Security and Reliability Reference

## Secrets and Access
- Keep credentials in platform secrets only.
- Rotate exposed credentials immediately.
- Use least-privilege access for DB and deployment roles.

## Reliability Baseline
- Health checks enabled.
- Daily backup verification.
- Alert on repeated 5xx spikes and DB connection failures.

## Incident Priorities
- P0: service down or data integrity risk.
- P1: severe degradation or repeated security anomalies.
- P2: non-critical errors with workaround.
