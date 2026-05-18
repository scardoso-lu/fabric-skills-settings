---
name: fabric-pipeline
description: Create, deploy, and test a Fabric Data Factory pipeline that chains all topic notebooks in order (download → bronze → dq_bronze → silver → dq_silver → gold → dq_gold). Use after all notebooks for a topic have been individually deployed and smoke-tested.
---

# fabric-pipeline

## MUST

- All notebooks for the topic must be deployed and individually smoke-tested before creating the pipeline
- Pipeline names follow the convention `pipeline_<topic>`
- Activities execute in strict order — each depends on its predecessor with `Succeeded`; failures never cascade
- For a **new** pipeline, always use `test` (create + run + monitor) — never report completion after `create` alone; activity wiring is only validated by a successful end-to-end run
- Use `create` alone only when the human explicitly says to skip the run (e.g. they will schedule the first run manually)
- Report STATUS: Completed or STATUS: Failed to orchestrator and stop — never re-run autonomously
- Each pipeline run consumes Fabric capacity; always await human approval before re-running a failed pipeline

## PREFER

- `test` command over separate `create` + `run` + `status` when running an existing pipeline
- Auto-discover over `--notebooks` — auto-discover reads naming conventions directly from the workspace
- Check the Fabric portal Run History for per-activity logs on failure

## AVOID

- Creating a pipeline before all its notebooks are deployed in Fabric
- Re-running on failure without human approval

## Commands

```bash
# Full cycle: auto-discover notebooks, create/update pipeline, run, and monitor
python tool/pipeline/manage.py test --topic lux_energy_price

# Create or update only (no run)
python tool/pipeline/manage.py create --topic lux_energy_price

# Explicit ordered list (use when auto-discover picks up the wrong notebooks)
python tool/pipeline/manage.py create --topic lux_energy_price \
    --notebooks download_lux_energy_price,bronze_lux_energy_price,dq_bronze_lux_energy_price

# Trigger an already-deployed pipeline (no monitoring)
python tool/pipeline/manage.py run --pipeline pipeline_lux_energy_price

# Monitor an existing run to completion
python tool/pipeline/manage.py status \
    --pipeline pipeline_lux_energy_price --instance <job-instance-id>

# List all data pipelines in the workspace
python tool/pipeline/manage.py list
```

## Activity Ordering

The tool sorts discovered notebooks by naming prefix. Use `--notebooks` to override.

| Prefix | Order | Layer responsibility |
|---|---|---|
| `download_` | 1 | Fetch source data to sandbox |
| `bronze_` | 2 | Ingest raw files to Bronze Delta |
| `dq_bronze_` | 3 | Validate Bronze layer |
| `silver_` | 4 | Clean and transform to Silver |
| `dq_silver_` | 5 | Validate Silver layer |
| `gold_` | 6 | Aggregate to Gold |
| `dq_gold_` | 7 | Validate Gold layer |

Notebooks that do not match a known prefix are appended at the end in alphabetical order.

## STATUS Handling

```
STATUS: Completed  → PASS — report to orchestrator
STATUS: Failed     → FAIL — report pipeline name, job instance ID, and failureReason.
                     STOP. Await human approval before any re-run.
STATUS: Cancelled  → report to orchestrator. Do not re-run without human approval.
```

For per-activity failure details: Fabric portal → Workspace → pipeline item → Run history → select the failed run.
