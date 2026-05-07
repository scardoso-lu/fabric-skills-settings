---
name: fabric-transform
description: Transform Bronze data into Silver — clean, deduplicate, enforce schema, and MERGE into Delta tables. Use when you need to cast types, apply business rules, handle nulls, or remove duplicates. DQ checks run in a separate dq_silver_<source>.py notebook using Great Expectations.
---

# fabric-transform

## MUST

- Cast all columns explicitly — never leave Bronze string types in Silver
- Use Delta MERGE for upserts — never plain APPEND to Silver
- Preserve lineage envelope columns from Bronze
- Log rows dropped due to null PKs — never drop silently

## PREFER

- `pyspark.sql.functions` over pandas for large datasets
- `mergeSchema=True` on MERGE operations for schema evolution
- Z-ORDER Silver tables by high-cardinality filter columns after bulk writes
- Null strategy: string fields → `""` or `"Unknown"`, numeric fields → keep null (never zero-fill)

## AVOID

- Dropping records silently — always log a count and reason before dropping
- Plain `df.write.mode("append")` in Silver (creates duplicates)
- `df.show()` or `print(df)` in production notebooks
- Zero-filling numeric nulls (hides data quality issues from downstream)
- Any DQ assertion logic — that belongs in the separate `dq_silver_<source>.py` notebook

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

df_cast = df.select(
    F.col("order_id").cast(IntegerType()).alias("order_id"),
    F.col("order_date").cast(TimestampType()).alias("order_date"),
    F.col("amount").cast(DecimalType(18, 2)).alias("amount"),
    F.col("_ingest_timestamp"),
    F.col("_source_system"),
    F.col("_batch_id"),
)

# Drop null PKs and log — DQ notebook (Great Expectations) asserts on Silver after the fact
null_pk_count = df_cast.filter(F.col("order_id").isNull()).count()
if null_pk_count > 0:
    print(f"[WARN] Dropping {null_pk_count} rows with null order_id before Silver write")
df_silver = df_cast.filter(F.col("order_id").isNotNull())
```

## Z-ORDER After Bulk Write

```python
spark.sql(f"OPTIMIZE delta.`{silver_path}` ZORDER BY (event_date, customer_id)")
```
