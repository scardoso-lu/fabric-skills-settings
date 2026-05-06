---
name: fabric-transform
description: Transform Bronze data into Silver — clean, deduplicate, enforce schema, and MERGE into Delta tables. Use when you need to cast types, apply business rules, handle nulls, remove duplicates, or move data from raw ingestion to enterprise-ready Silver layer. Also handles quarantine routing for records that fail quality gates.
---

# fabric-transform

## MUST

- Cast all columns explicitly — never leave Bronze string types in Silver
- Use Delta MERGE for upserts — never plain APPEND to Silver
- Route records failing DQ gates to `<table>_quarantine` table
- Preserve lineage envelope columns from Bronze
- Validate primary keys — rows with null PKs must be dropped and quarantined

## PREFER

- `pyspark.sql.functions` over pandas for large datasets
- `mergeSchema=True` on MERGE operations for schema evolution
- Z-ORDER Silver tables by high-cardinality filter columns after bulk writes
- Null strategy: string fields → `""` or `"Unknown"`, numeric fields → keep null (never zero-fill)

## AVOID

- Dropping records silently — always route to quarantine with a reason
- Plain `df.write.mode("append")` in Silver (creates duplicates)
- `df.show()` or `print(df)` in production notebooks
- Zero-filling numeric nulls (hides data quality issues from downstream)

## MERGE Pattern

```python
from delta.tables import DeltaTable

silver = DeltaTable.forPath(spark, silver_path)

silver.alias("target").merge(
    source=df.alias("source"),
    condition="target.order_id = source.order_id"
).whenMatchedUpdate(
    condition="source._ingest_timestamp > target._ingest_timestamp",
    set={"col1": "source.col1", "col2": "source.col2", "_ingest_timestamp": "source._ingest_timestamp"}
).whenNotMatchedInsertAll(
).execute()
```

## Type Casting Pattern

```python
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, TimestampType, DecimalType

good_df = df.select(
    F.col("order_id").cast(IntegerType()).alias("order_id"),
    F.col("order_date").cast(TimestampType()).alias("order_date"),
    F.col("amount").cast(DecimalType(18, 2)).alias("amount"),
    F.col("_ingest_timestamp"),
    F.col("_source_system"),
    F.col("_batch_id"),
)

# Quarantine rows that failed casting (nulls where not nullable)
quarantine_df = good_df.filter(F.col("order_id").isNull())
good_df = good_df.filter(F.col("order_id").isNotNull())
```

## DQ Gates

```python
def check_range(df, col, min_val, max_val):
    bad = df.filter(~F.col(col).between(min_val, max_val))
    good = df.filter(F.col(col).between(min_val, max_val))
    return good, bad

good_df, quarantine_age = check_range(good_df, "age", 0, 150)
```

## Z-ORDER After Bulk Write

```python
spark.sql(f"OPTIMIZE delta.`{silver_path}` ZORDER BY (event_date, customer_id)")
```
