---
name: pipeline-structure
description: Required base/silver/ML notebook structure per topic. Never collapse layers; each notebook owns one responsibility.
kind: content
links:
  - graph-content/semantic/semantic-models
  - skills/fabric-transform
  - skills/fabric-validate
  - skills/fabric-model
---

# Pipeline structure

Every data source topic starts with exactly three notebooks. Topics that proceed to analytics or ML add layers on top — each layer in its own notebook, never collapsed.

## Base layer (always required)

| Notebook | Naming | Responsibility |
|---|---|---|
| Download | `download_<source>.py` | Call source API, skip existing sandbox files, save raw files as-is. No Spark. No Delta writes. Print existing, downloaded, and failed counts. |
| Ingestion | `bronze_<source>.py` | Read sandbox files, compare against Bronze Delta table, process only new files, then MERGE or partition-overwrite. Never full-overwrite. |
| Data quality | `dq_bronze_<source>.py` | Great Expectations checks for row count, null PKs, duplicate PKs, schema match, and business sanity. Print structured PASS/FAIL per check and raise on any failure. |

## Silver layer (optional — clean and conformed)

| Notebook | Naming | Responsibility |
|---|---|---|
| Silver transform | `silver_<source>.py` | SQL-first MERGE from bronze into `silver_<source>` Delta. Cast all columns explicitly. Dedup by PK keeping latest `_ingest_ts`. Drop null-PK rows with a logged count (never silent). Derive computable columns from authoritative timestamps; do NOT cast bronze columns whose type may have drifted. |
| Silver DQ | `dq_silver_<source>.py` | Row count, no null PKs, no duplicate PKs, schema match, business range checks. PASS/FAIL with raise. |

## ML layer (optional — forecasting / scoring)

| Notebook | Naming | Responsibility |
|---|---|---|
| Features | `features_<source>.py` | Build feature Delta table from silver. Lag columns, rolling stats, calendar attributes. MERGE on PK. |
| Features DQ | `dq_features_<source>.py` | PK uniqueness, target presence, lag-coverage thresholds, schema match. |
| Train | `train_<source>.py` | Train model, log params/metrics/artifact to MLflow, register model. **Runs interactively in Fabric UI only** — SPN-triggered runs fail with `MwcTokenValidationException`. See `memory/skill-fixes/fabric-mlflow-spn-blocked.md`. MLflow experiment names: only `[A-Za-z0-9_-]`, must start with letter/digit. See `memory/skill-fixes/fabric-mlflow-experiment-name.md`. |
| Predict | `predict_<source>.py` | Load registered model from MLflow, score the forecast horizon, write `forecast_<source>` Delta. Also runs interactively when it uses `models:/.../latest`. For closed-loop scoring, switch persistence to `joblib` under `Files/models/`. |

A single notebook that combines two of these responsibilities is always wrong. The developer agent may create DQ notebook scaffolds; the tester agent owns independent validation logic and final DQ validation.

For Gold facts/dimensions and Power BI semantic models exposing topic tables, see [[graph-content/semantic/semantic-models]].
