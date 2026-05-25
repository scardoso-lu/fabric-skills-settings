---
name: semantic-models
description: Direct Lake semantic model authoring constraints (no calculated columns/tables). TMDL is the source of truth in repo; humans paste into Fabric UI.
kind: content
links:
  - skills/semantic-model
  - skills/fabric-model
---

# Semantic models

Semantic models (Power BI datasets) live under `workspace/<topic>/semantic-model/` and have two files:

- `<model>.tmdl` — authoritative TMDL definition: column mappings, format strings, hidden columns, DAX measures
- `README.md` — UI walkthrough to create the Direct Lake model from the underlying lakehouse table and paste the TMDL

Per the [[skills/semantic-model]] skill, **agents do not create or modify semantic models via REST API**. Author TMDL in the repo as the source of truth; humans create the Direct Lake model in the Fabric UI ("New semantic model" from the lakehouse) and paste the TMDL via the editor's TMDL view. Re-runs of the source predict/transform notebooks update the model via Direct Lake automatically.

## Direct Lake limitations

- **No calculated columns** — every visible column must come from the underlying Delta table.
- **Measures (pure DAX) are fully supported.**
- **Hide engineering/lineage columns** (`_ingest_ts`, lag columns, raw tracking fields) via `isHidden`.
- **Calculated tables**: not supported. Materialize upstream in a notebook.
- **Calculated-column-based RLS**: not supported. Move the predicate column into the Delta table.

If the model needs `is_weekend`, `hour_of_day`, `price_date_lu`, etc., produce that column upstream in the silver or features notebook and expose it through `sourceColumn` — never derive it inside the TMDL.

See `memory/skill-fixes/directlake-no-calculated-columns.md` for the incident this rule comes from.
