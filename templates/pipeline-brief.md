---
name: pipeline-brief
description: Lightweight pipeline-design brief — source, target layers, contracts, thresholds, owner, and stop conditions.
kind: template
---

# Pipeline Brief

## Business Purpose

*What problem does this pipeline solve? What decision does it enable?*

## Source

- **System**: 
- **Data**: 
- **Cadence**: 
- **Volume**: 

## Expected Output

- **Target table(s)**: 
- **Grain**: (what does one row represent?)
- **Key metrics or columns produced**: 

## Constraints

- **Deadline**: 
- **Sensitive fields**: 
- **Existing dependencies**: 
- **Schema contracts to preserve**: 

## Success Criteria

- [ ] Row count within expected range
- [ ] No null primary keys
- [ ] No duplicates on business keys
- [ ] Sensitive fields masked
- [ ] Audit envelope present on all rows
- [ ] Downstream reports/dashboards unaffected
