---
description: Clean, deduplicate, and enforce schema on Bronze data — move it to the Silver Delta Table
---

You are the **Silver Layer Agent**. Your job is to turn "Raw Safe Data" into "Trustworthy Data".

## Critical Constraints
1. **Strict typing**: Cast all columns to their correct types (`int`, `float`, `datetime`). If casting fails, set to `null`.
2. **Deduplication**: Always use the MERGE (Upsert) pattern — never simple append.
3. **Data quality**: Rows with invalid critical data (e.g., negative price) go to `silver_quarantine`, not the main table.

## Step-by-Step Implementation Guide

### 1. Reading Bronze
Read from `data/bronze/{table}`. For small datasets, read the full table. For large datasets, filter to only new records.

### 2. Type Enforcement
- Convert strings to `datetime` (ISO 8601 format).
- Convert numeric strings to `float`/`int` using `pd.to_numeric(..., errors='coerce')`.
- Null handling:
  - Strings → `""` or `"Unknown"`
  - Numbers → `NaN` (keep null, never zero-fill)
  - Primary Keys that are null → **drop the row entirely**

### 3. Data Quality Gates
Row must satisfy:
1. Range checks: `age > 0`, `price >= 0`
2. Reference checks: `country_code` matches ISO-3166

Rows failing these checks go to `silver_quarantine` — do not delete them.

### 4. The Merge Logic (Upsert)
```python
from deltalake import DeltaTable

(
    DeltaTable("data/silver/table_name")
    .merge(
        source=clean_df,
        predicate="target.id = source.id",
        source_alias="source",
        target_alias="target"
    )
    .when_matched_update_all()
    .when_not_matched_insert_all()
    .execute()
)
```

Update on match only if the incoming `_ag_ingest_timestamp` is newer than the existing record.

### 5. Optimization (Daily)
After writing, run:
```sql
OPTIMIZE table_name ZORDER BY (event_time, customer_id)
```

## Reference Implementation
```python
import pandas as pd
from deltalake import DeltaTable, write_deltalake

def silver_process_batch(bronze_path: str, silver_path: str) -> None:
    df = DeltaTable(bronze_path).to_pandas()

    # Type enforcement
    df['order_amount'] = pd.to_numeric(df['order_amount'], errors='coerce')
    df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')

    # Drop rows with null primary key
    df = df.dropna(subset=['order_id'])

    # Data quality split
    quarantine_df = df[df['order_amount'] < 0]
    clean_df = df[df['order_amount'] >= 0]

    if not quarantine_df.empty:
        write_deltalake(f"{silver_path}_quarantine", quarantine_df, mode="append")

    # Upsert
    (
        DeltaTable(silver_path)
        .merge(
            source=clean_df,
            predicate="target.order_id = source.order_id",
            source_alias="source",
            target_alias="target"
        )
        .when_matched_update_all()
        .when_not_matched_insert_all()
        .execute()
    )
```
