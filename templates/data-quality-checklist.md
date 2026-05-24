---
name: data-quality-checklist
description: Per-layer DQ checklist — row counts, null PKs, duplicate PKs, schema match, business-range checks.
kind: template
---

# Data Quality Checklist

Environment:

## Required Checks

- [ ] Row count from source/Bronze/Silver/Gold reconciled.
- [ ] Duplicate check at declared grain.
- [ ] Primary/business key null check.
- [ ] Schema drift check.
- [ ] DQ notebook (`dq_<layer>_<source>.py`) ran and all GX expectations passed.
- [ ] Referential integrity checked where relevant.
- [ ] Metrics reconcile to expected examples.
- [ ] Sensitive fields masked, excluded, or protected.
- [ ] Validation evidence attached to handoff.

## Results

| Check | Query/Command | Expected | Actual | Pass/Fail | Notes |
| --- | --- | --- | --- | --- | --- |

