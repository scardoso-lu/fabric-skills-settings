---
name: fabric-notebook-loop-mlflow-platform-limits
description: Fabric MLflow platform constraints — experiment name validation rules and the SPN-token MwcTokenValidationException that blocks closed-loop MLflow runs.
kind: content
links:
  - skills/fabric-notebook-loop
  - skills/fabric-notebook-loop/prefer-avoid
---

# MLflow in Fabric — Platform Limits

Two distinct Fabric-MLflow issues affect any `train_<source>.py` / `predict_<source>.py` notebook in the closed loop.

## 1. Experiment names are validated before open-source MLflow

`mlflow.set_experiment(name)` goes through Fabric's `TridentMLflowTrackingStore.check_experiment_name_valid` first. Allowed:

- Length: < 257 chars
- First char: letter or digit (NOT `/`, `-`, `_`)
- Remaining chars: alphanumeric, `-`, `_` only

Do NOT copy Databricks `/Shared/...` patterns. A leading `/`, a `.`, or a space all fail. Use flat slugs prefixed by topic, e.g. `lux_energy_price_day_ahead`. See `memory/skill-fixes/fabric-mlflow-experiment-name.md`.

## 2. SPN-authenticated runs cannot use MLflow at all

Notebooks submitted via `fab-sandbox` run as a Service Principal. Fabric's MLflow plugin calls a backend "Mwc" service that rejects SPN tokens:

```
RestException: INTERNAL_ERROR: Response:
{'Message': 'Internal error MwcTokenValidationException.', 'Source': 15, 'ErrorCode': 0}
```

Anything that talks to the Fabric MLflow tracking server fails for SPN runs:
- `mlflow.set_experiment`, `mlflow.start_run`, `mlflow.log_*`
- `mlflow.lightgbm.log_model` / `mlflow.sklearn.log_model` (uses tracking under the hood)
- `mlflow.tracking.MlflowClient().get_latest_versions(...)`

The same notebook works fine when executed interactively as a human user in the Fabric UI. This is a Fabric platform limit, not an SDK bug.

**Decision rule for ML notebook persistence:**

| Notebook will be… | Persistence strategy |
|---|---|
| Smoke-tested in the closed loop (`deploy.py exec` / `smoke-test.ps1`) | **Must use file-based persistence** — `joblib.dump` to `/lakehouse/default/Files/models/<topic>/<name>_<ts>.pkl` + a `_latest.pkl` pointer. Do NOT call MLflow. |
| Run interactively in Fabric UI by a human | MLflow is fine. Make the human-only execution explicit upfront. |

Closed-loop pickle pattern:

```python
import os, joblib
from datetime import datetime

MODEL_DIR = "/lakehouse/default/Files/models/<topic>"
os.makedirs(MODEL_DIR, exist_ok=True)
ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
joblib.dump(
    {"model": model, "feature_cols": FEATURE_COLS, "metrics": {...}, "trained_at": ts},
    f"{MODEL_DIR}/<model_name>_{ts}.pkl",
)
joblib.dump(..., f"{MODEL_DIR}/<model_name>_latest.pkl")
```

See `memory/skill-fixes/fabric-mlflow-spn-blocked.md` for the incident this rule comes from.
