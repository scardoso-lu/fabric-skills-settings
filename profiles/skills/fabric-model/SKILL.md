---
name: fabric-model
description: Build Gold layer analytical objects — dimensional models (Kimball star schema), KPI aggregates, wide tables, or TMDL semantic models. Use when creating fact tables, dimension tables, monthly aggregates, or Power BI semantic models from Silver data. Enforces referential integrity, metric standardization, and schema locking.
---

# fabric-model

## MUST

- Define business metrics in Gold — never in the BI tool or downstream
- Verify dimension key existence before writing fact rows (referential integrity gate)
- Link orphan facts to the `-1` / `Unknown` dimension key — never drop fact rows
- Run `OPTIMIZE` with `ZORDER` after every Gold write
- Gold schemas are a contract — schema changes require explicit approval and backfill plan

## PREFER

- Kimball star schema (fact + dimension tables) for standard reporting
- One atomic fact table at lowest grain + aggregate tables for KPIs
- Delta Lake tables over views for materialized Gold
- Separate lakehouse for Gold layer (independent access control)
- `DELETE + INSERT` over MERGE in Fabric Warehouse (MERGE is preview)

## AVOID

- Business logic (churn definition, LTV formula) in Power BI DAX — define it in Gold
- Dropping fact rows when dimension is missing — use Unknown dimension key
- Plain APPEND on Gold tables (creates duplicates on re-run)
- Overloading fact tables with descriptive attributes (put them in dimensions)

## Dimensional Model Pattern

```python
# Dimension table (slowly changing, type 1 overwrite)
dim_customers = silver_customers.select(
    F.col("customer_id"),
    F.col("customer_name"),
    F.col("region"),
    F.col("segment"),
    F.current_timestamp().alias("_dim_updated_at"),
).dropDuplicates(["customer_id"])

(dim_customers.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "false")  # schema is locked
    .save(dim_path)
)

# Fact table with RI gate
unknown_customer_id = -1

fact_orders = (silver_orders
    .join(dim_customers.select("customer_id"), on="customer_id", how="left")
    .withColumn("customer_key",
        F.when(F.col("customer_id").isNotNull(), F.col("customer_id"))
         .otherwise(F.lit(unknown_customer_id))
    )
)

(fact_orders
    .write.format("delta")
    .mode("overwrite")
    .partitionBy("order_month")
    .save(fact_path)
)
```

## Gold Optimization (always run after write)

```python
spark.conf.set("spark.sql.parquet.vorder.enabled", "true")
spark.conf.set("spark.microsoft.delta.optimizeWrite.enabled", "true")
spark.sql(f"OPTIMIZE delta.`{fact_path}` ZORDER BY (order_date, region_id)")
```

## KPI Aggregate Pattern

```python
kpi_monthly = (fact_orders
    .groupBy(
        F.date_format("order_date", "yyyy-MM").alias("month"),
        F.col("region_id")
    )
    .agg(
        F.sum("revenue").alias("total_revenue"),
        F.countDistinct("customer_id").alias("active_customers"),
        F.count("order_id").alias("order_count"),
    )
)
```
