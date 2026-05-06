# Fabric Sandbox Smoke Test Runbook

This is a human-run smoke test for a sandbox Fabric workspace. It is a local human-run checklist, does not require committed credentials, and must not target production.

## Preconditions

- `fab` is installed and the human has run `fab auth login`.
- `.env` contains placeholder-filled sandbox IDs only; do not paste IDs into chat.
- A sandbox workspace exists with `bronze_lh`, `silver_lh`, and `gold_lh` lakehouses.
- The operator is involved before any production or permission change.

## Read-only inventory

Run locally:

```bash
bin/fabric-inventory-readonly
bin/fabric-inventory-readonly --workspace-id "$FABRIC_WORKSPACE_ID" --items
```

Review the output locally. Copy approved sandbox IDs into `.env` yourself; agents must not receive or write real environment-specific IDs.

## Notebook smoke test

1. Create a tiny local notebook under `src/notebooks/` using synthetic data only.
2. Build notebooks:
   ```bash
   python3 bin/build_fabric_notebooks.py
   ```
3. Import the notebook to the sandbox workspace with `fab` or `bin/fab-sandbox`.
4. Run the notebook in the sandbox workspace.
5. Capture the run ID from `fab` output.
6. Inspect the run with `nbmon status <run-id>`.
7. Confirm no real source data, credentials, or PII appears in notebook output.

## Memory updates

After a successful smoke test, update:

- `memory/platform.md` for any durable sandbox Fabric item.
- `memory/project.md` for the smoke test result.
- `memory/decisions.md` for non-obvious setup choices.

## Cleanup

Delete temporary sandbox test items through the Fabric portal or `fab` after recording any durable items that remain. Do not delete shared sandbox lakehouses unless the team explicitly agrees.
