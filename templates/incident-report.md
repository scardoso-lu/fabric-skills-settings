---
name: incident-report
description: Post-incident write-up — timeline, impact, root cause, remediation, and action items.
kind: template
---

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

## DQ Failure Investigation Playbook

Use this section when tester escalates a failed GX expectation from a `dq_<layer>_<source>.py` notebook.

1. Confirm the affected pipeline, table, batch ID, and the failed GX expectation name.
2. Classify the failure type:
   - **Schema mismatch**: source contract drift, missing column, unexpected type, or parser failure.
   - **Null/duplicate failure**: null PK, duplicate key, or required field null.
   - **Business rule failure**: impossible date, negative metric, or failed range check.
   - **PII/masking failure**: raw sensitive field found, masked field leaked to logs, or sanitization barrier bypassed.
3. If PII or masking is involved, trigger the deletion/toxic-data path from `rules/security.md` and keep raw values out of the report.
4. If schema or data quality failure, hand back to developer with the exact failed expectation name and affected batch ID.
5. Record the final verdict and remediation in `memory/security/<scope>.md`.

