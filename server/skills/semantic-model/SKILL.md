---
name: semantic-model
description: List, read, and interpret Microsoft Fabric Semantic Models (Power BI datasets). Use when an agent needs to understand available business metrics, DAX measures, table relationships, or column definitions before writing DAX queries, building reports, or validating Gold-layer outputs against business definitions.
---

# semantic-model

## When to use

Invoke before any task that depends on understanding business metric definitions:

- Writing or reviewing a DAX query or measure
- Checking whether a Gold-layer table covers a KPI already defined in a semantic model
- Understanding join paths (relationships) before recommending aggregation logic
- Validating that a Silver → Gold promotion matches the expected column names and types
- Answering questions like "what does the Revenue measure include?" or "how is Churn Rate calculated?"

## Tools — `semantic_model_list` / `semantic_model_show` (MCP)

Inspection runs server-side via the `fabric-server` MCP tools (backed by
`sempy.fabric` in the container). There is no target-side script. Auth is
handled by the container's service-principal credentials.

| Tool | Arguments | Purpose |
|---|---|---|
| `semantic_model_list` | _(none — uses the configured `FABRIC_WORKSPACE_ID`)_ | List all semantic models in the workspace |
| `semantic_model_show` | `model` (name or id); `include_hidden` (default off); `include_expressions` (default off — DAX may carry sensitive logic) | Show tables, columns, measures, and relationships for one model. Always returns JSON. |

Call `semantic_model_list` first when the model name is unknown — never guess
an ID. `semantic_model_show` hides DAX expressions and hidden objects by
default; opt in with `include_expressions` / `include_hidden` only when needed.

## Output format

### list

```
Name                                           ID                                    Description
---------------------------------------------------------------------------------------------------------
Sales Model                                    a1b2c3d4-...                          Core revenue and margin KPIs
```

### show

```
Semantic Model : Sales Model
ID             : a1b2c3d4-...
Description    : Core revenue and margin KPIs

  Table: Date
    col  Date                                    DateTime
    col  Year                                    Int64
    col  Month                                   Int64
    col  MonthName                               String         [calc]  = FORMAT([Date], "MMMM")

  Table: Sales
    col  OrderID                                 Int64
    col  CustomerKey                             Int64
    col  Amount                                  Decimal
    mea  Total Revenue                           SUM(Sales[Amount])  [#,##0.00]  // Gross before returns
    mea  Net Revenue                             [Total Revenue] - [Returns]

  Relationships:
    Sales[CustomerKey]  →  Customer[CustomerKey]  [BothDirections]
    Sales[DateKey]      →  Date[DateKey]
```

## How to interpret

| Symbol | Meaning |
|---|---|
| `col` | Regular or calculated column |
| `mea` | DAX measure |
| `[calc]` | Calculated column (DAX expression shown after `=`) |
| `[hidden]` | Hidden from report view — internal use only |
| `[inactive]` | Relationship exists but is not the active join path; use `USERELATIONSHIP()` in DAX |
| `[BothDirections]` | Cross-filter propagates both ways — watch for ambiguous paths |

## What to derive from the output

- **Measure expressions** are the authoritative business definitions. When a Gold table computes the same metric, the DAX and the PySpark logic must agree.
- **Relationships** define valid join paths. A missing relationship is a schema gap; an inactive relationship requires explicit `USERELATIONSHIP()`.
- **Hidden columns** are implementation details. Do not surface them in reports or Silver/Gold schemas.
- **Data types** on columns must match what Bronze/Silver produce. A `Decimal` column fed an `Int64` source will silently truncate.

## MUST

- Run `list` first when the model name is unknown — never guess an ID
- Always confirm the model exists in this workspace before referencing its measures in code or documentation
- Treat measure expressions as read-only — the semantic model is owned by the BI team, not the data engineering agent
- For new Direct Lake models authored in this repo, keep TMDL under `workspace/<topic>/semantic-model/<model>.tmdl` as the source of truth and a sibling `README.md` with the Fabric UI creation walkthrough
- Author TMDL with **only** columns that map to real Delta columns via `sourceColumn` — no calculated columns, no calculated tables (Direct Lake constraint)
- Move any per-row derivation (`is_weekend`, `hour_of_day`, `price_date_lu`) **upstream into the silver or features notebook** so the model only consumes existing Delta columns

## AVOID

- Modifying semantic models via REST API — use the Fabric UI or XMLA endpoint under human supervision
- Assuming a measure in one model is defined identically in another — always inspect the target model directly
- Declaring a calculated column in Direct Lake TMDL (`column 'X' = <DAX>`) — it silently degrades the model to DirectQuery or fails the TMDL save
- Calculated tables in Direct Lake — not supported
- Row-level security using calculated-column predicates in Direct Lake — not supported

## Direct Lake authoring constraints

When authoring a Direct Lake semantic model from a forecast / silver / gold Delta table:

| Allowed in Direct Lake | Use for |
|---|---|
| Measures (pure DAX over the table) | All per-aggregation logic — `SUM`, `AVERAGE`, `CALCULATE(..., <filter>)` |
| `sourceColumn` → `name` mapping | Renaming a Delta column to a friendly label without altering the underlying schema |
| `formatString`, `summarizeBy`, `isHidden` | Display, summarization defaults, hiding lineage/tracking columns |

| NOT allowed in Direct Lake | Workaround |
|---|---|
| Calculated columns (`column 'X' = <expr>`) | Add the column to the upstream Delta table in the silver or features notebook |
| Calculated tables | Materialize the table upstream in a notebook and point the model at the resulting Delta table |
| Calculated-column-based RLS | Move the predicate column into the Delta table; use measure-level filters in DAX |

If the model needs `is_weekend`, `hour_of_day`, `price_date_lu`, etc., produce that column upstream and expose it through `sourceColumn` — never derive it inside the TMDL.

See `memory/skill-fixes/directlake-no-calculated-columns.md` for the incident this rule comes from.

## TMDL repo workflow

The `semantic-model` skill does NOT create or modify semantic models via REST API. The workflow is:

1. Author `<model>.tmdl` and `README.md` under `workspace/<topic>/semantic-model/`.
2. Human creates the Direct Lake model in the Fabric UI ("New semantic model" from the underlying lakehouse).
3. Human pastes the TMDL into the editor's TMDL view to apply column mappings and measures.
4. Subsequent runs of the upstream notebooks update the model automatically via Direct Lake — no re-paste needed unless TMDL changes.
