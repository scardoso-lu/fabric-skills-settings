---
name: fabric-validate
description: Validate pipeline output with repeatable data quality checks — row counts, null PKs, duplicates, schema drift, quarantine rates, referential integrity, and business metric sanity. Use after any pipeline run to confirm data correctness before downstream consumption. Produces a structured validation report.
---

# fabric-validate

## MUST

- Run all checks independently — never rely on developer's implementation for validation logic
- Produce a structured report with PASS/FAIL per check
- Read `config/thresholds.yaml` for all threshold values — never hardcode them
- Quarantine rate above `dq.quarantine_rate_pct` must trigger escalation — never approve silently
- Check both current run AND comparison to previous run (row count delta, metric drift)

## Standard Check Suite

```sql
-- 1. Row count
SELECT COUNT(*) AS row_count FROM silver_orders;

-- 2. Null primary keys
SELECT COUNT(*) AS null_pks FROM silver_orders WHERE order_id IS NULL;

-- 3. Duplicates on business key
SELECT order_id, COUNT(*) AS cnt
FROM silver_orders
GROUP BY order_id
HAVING COUNT(*) > 1;

-- 4. Quarantine rate
SELECT 
    COUNT(*) AS quarantined,
    (COUNT(*) * 100.0 / (SELECT COUNT(*) FROM silver_orders)) AS quarantine_pct
FROM silver_orders_quarantine
WHERE _batch_id = '<current_batch>';

-- 5. Null rate on key fields
SELECT 
    SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS amount_null_pct
FROM silver_orders;

-- 6. Range check
SELECT COUNT(*) FROM silver_orders WHERE amount < 0;

-- 7. Referential integrity (Gold)
SELECT COUNT(*) FROM fact_orders f
LEFT JOIN dim_customers d ON f.customer_key = d.customer_id
WHERE d.customer_id IS NULL;

-- 8. Audit envelope presence
SELECT COUNT(*) FROM silver_orders 
WHERE _ingest_timestamp IS NULL 
   OR _source_system IS NULL 
   OR _batch_id IS NULL;
```

## PySpark Version

```python
def run_dq_checks(df, table_name: str, pk_col: str) -> dict:
    results = {}
    
    total = df.count()
    results['row_count'] = total
    results['null_pks'] = df.filter(F.col(pk_col).isNull()).count()
    results['duplicates'] = (df.groupBy(pk_col).count()
                               .filter(F.col("count") > 1).count())
    results['missing_envelope'] = df.filter(
        F.col("_ingest_timestamp").isNull() |
        F.col("_source_system").isNull() |
        F.col("_batch_id").isNull()
    ).count()
    
    return results
```

## Validation Report Template

```markdown
## Validation Report
- **Table**: silver_orders
- **Batch ID**: <uuid>
- **Run date**: <timestamp>
- **Records processed**: <n>
- **Quarantine rate**: <n>%

| Check | Status | Value | Threshold | Detail |
|---|---|---|---|---|
| Row count | PASS | 10,432 | >0 | |
| Null PKs | PASS | 0 | =0 | |
| Duplicates | PASS | 0 | =0 | |
| Quarantine rate | PASS | 1.2% | <5% | |
| Null amount | PASS | 0.3% | <2% | |
| Range check (amount ≥ 0) | PASS | 0 violations | =0 | |
| Audit envelope | PASS | 0 missing | =0 | |

**Anomalies**: none
**Recommendation**: PASS
```

## Anomaly Thresholds

Thresholds are defined in `config/thresholds.yaml`. Default values are shown below — always read the file at runtime.

| Metric | Config key | Default | Action |
|---|---|---|---|
| Row count drop vs. previous run | `dq.row_count_drop_pct` | >20% | FAIL — escalate to developer |
| Quarantine rate | `dq.quarantine_rate_pct` | >5% | ESCALATE TO OPERATOR |
| Null rate spike on key field | `dq.null_rate_spike_pct` | >10% | FAIL — escalate to developer |
| RI failures (fact → dim) | `dq.ri_failure_pct` | >5% | FAIL — escalate to developer |
| Missing audit envelope | `anomaly.max_missing_envelope` | Any (>0) | FAIL — escalate to developer |
