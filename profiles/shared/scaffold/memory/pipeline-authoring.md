# Pipeline Authoring — Conventions and Gotchas

## Parameter injection into TridentNotebook activities

Use `workspace/<topic>/pipeline_params.json` to define the parameter schema.
Values are embedded directly in each activity's `typeProperties.parameters`:

```json
{"value": "actual_value", "type": "string"}
```

Do NOT use `@pipeline().parameters.X` — Fabric does not interpolate pipeline
parameter references into TridentNotebook activity parameters.

CI/CD substitutes env-specific values in `pipeline_params.json` before deployment.
Commit only neutral defaults (empty strings for secrets).

### pipeline_params.json schema

```json
{
  "parameters": {
    "WAREHOUSE_HOST": "",
    "WAREHOUSE":      "DATA_WAREHOUSE",
    "LAKEHOUSE":      "DATALAKE",
    "DBT_REPO_URL":   "https://github.com/example/repo.git",
    "SANDBOX_DIR":    "Files/data/sandbox/my_topic"
  }
}
```

### CLI usage

```bash
# Create pipeline using pipeline_params.json values
python tool/pipeline/manage.py create --topic my_topic

# Override a specific value at invocation time (e.g. dev WAREHOUSE_HOST in manual testing)
python tool/pipeline/manage.py create --topic my_topic \
    --params WAREHOUSE_HOST=<dev-tds-endpoint>

# Full test cycle (create + run + monitor)
python tool/pipeline/manage.py test --topic my_topic \
    --params WAREHOUSE_HOST=<dev-tds-endpoint>
```

`--params` values override `pipeline_params.json` values; the file values are the base.
`run` subcommand does not accept `--params` — parameters are embedded at `create` time.
