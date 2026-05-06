# Incident Report

## Summary

- Date/time:
- Environment:
- Asset:
- Severity:
- Status:

## Impact

-

## Timeline

| Time | Event |
| --- | --- |

## Root Cause

-

## Recovery

-

## Follow-Up

- [ ] Runbook updated.
- [ ] Validation added or improved.
- [ ] Security/access reviewed if relevant.
- [ ] Platform inventory updated.

## Quarantine Investigation Playbook

Use this section when tester escalates because quarantine rate is greater than 5%.

1. Confirm the affected pipeline, table, batch ID, and quarantine rate.
2. Query quarantine reasons without exposing raw sensitive values:

```sql
SELECT _batch_id, _quarantine_reason, COUNT(*) AS cnt
FROM <table>_quarantine
WHERE _batch_id = '<batch-id>'
GROUP BY _batch_id, _quarantine_reason
ORDER BY cnt DESC;
```

3. Classify the dominant reason:
   - **Schema mismatch**: source contract drift, missing column, unexpected type, or parser failure.
   - **Validation rule failure**: null PK, duplicate key, impossible date, negative metric, or failed range check.
   - **PII/masking failure**: raw sensitive field found, masked field leaked to logs, or sanitization barrier bypassed.
4. If PII or masking is involved, trigger the deletion/toxic-data path from `rules/security.md` and keep raw values out of the report.
5. If schema or validation is involved, hand back to developer with the exact failed rule and affected batch ID.
6. Record the final verdict and remediation in `.codex-fabric/memory/security/<scope>.md`.

