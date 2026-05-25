---
name: notebook-authoring
description: Mandatory notebook authoring rules — file paths, packages, multi-notebook pipelines, mssparkutils detection, and three-notebook structure per topic.
kind: rule
---

# Notebook Authoring Rules

Read at the start of every session. These rules apply to every notebook written or edited in this repository.

## Fabric file paths

Use lakehouse-relative paths: `Files/data/sandbox/...`. Never use `/lakehouse/default/Files/...` absolute paths — `mssparkutils` rejects them.

## Non-standard packages

Add `%pip install "pkg>=x,<y"` as the **first cell** (`# %% [install]`) of any notebook that needs packages not in the Fabric Spark runtime (e.g. `great_expectations`, `requests`, `lxml`). `deploy.py` enables `_inlineInstallationEnabled` automatically for API-triggered runs so `%pip` cells execute.

## Multi-notebook pipelines

`SOURCE_DIR` in a downstream notebook must exactly match `OUTPUT_DIR` in the upstream notebook. A path mismatch produces a silent empty read — no error, just missing data. After any staging-path change, run:

```bash
python tool/validate/pipeline-lineage.py
```

A FAIL must be fixed before building or deploying.

## Fabric vs local paths

Use `mssparkutils` detection to write portable code that runs both in Fabric and locally:

```python
try:
    from notebookutils import mssparkutils; IS_FABRIC = True
except ImportError:
    IS_FABRIC = False
OUTPUT_DIR = "Files/data/sandbox/<topic>" if IS_FABRIC else "data/sandbox/<topic>"
```

## Pipeline structure

Every data source topic requires exactly three notebooks — no exceptions:

| Notebook | Naming | Responsibility |
|---|---|---|
| Download | `download_<source>.py` | Call source API → skip existing sandbox files → save raw files as-is. No Spark. No Delta writes. |
| Ingestion | `bronze_<source>.py` | Read sandbox files → compare against Bronze Delta table → process only new files → MERGE or partition-overwrite. Never full-overwrite. |
| Data quality | `dq_bronze_<source>.py` | Great Expectations checks. Print structured PASS/FAIL per check. Raise on any FAIL. |

A single notebook that downloads + ingests + overwrites is always wrong.
