# Platform Inventory

<!-- Agents: add an entry every time you create a Fabric item. Keep this current. -->
<!-- If an item is deleted or renamed, update or remove its entry. -->
<!-- Example below — delete or replace after your first real platform/source entry. -->

## Workspaces

| Name | Type | Purpose | Owner |
|---|---|---|---|
| *(none yet)* | | | |
<!-- Example: | fabric-sandbox | Workspace | Agent-built development only | data-engineering | -->

## Lakehouses

| Name | Workspace | Layer | Created | Notes |
|---|---|---|---|---|
| *(none yet)* | | | | |
<!-- Example: | bronze_lh | fabric-sandbox | Bronze | 2026-05-06 | Raw + masked ingest tables | -->

## Warehouses

| Name | Workspace | Purpose | Created |
|---|---|---|---|
| *(none yet)* | | | |
<!-- Example: | analytics_wh | fabric-sandbox | Serving SQL marts | 2026-05-06 | -->

## Notebooks

| Name | Workspace | Lakehouse | Schedules | Runbook |
|---|---|---|---|---|
| *(none yet)* | | | | |
<!-- Example: | nb_orders_bronze | fabric-sandbox | bronze_lh | manual | memory/runbooks/orders-bronze.md | -->

## Data Factory Pipelines

| Name | Workspace | Trigger | Dependencies |
|---|---|---|---|
| *(none yet)* | | | |
<!-- Example: | pl_orders_medallion | fabric-sandbox | manual/day-one | nb_orders_bronze → nb_orders_silver | -->

## Source Systems

| Name | Type | Env Var Prefix | Cadence | Sensitive Fields |
|---|---|---|---|---|
| *(none yet)* | | | | |
<!-- Example: | ORDERS | file | SRC_ORDERS | ad hoc sandbox | customer_name, email | -->

## Source Registration Template

When adding a source system, register it here and add placeholder-only variables to `.env` (or `.env.example` when changing the reusable template):

```bash
SRC_<SYSTEM>_TYPE=file
SRC_<SYSTEM>_PATH=./data/sandbox/<filename>.csv
```

Never write real hosts, passwords, tokens, or connection strings to memory.
