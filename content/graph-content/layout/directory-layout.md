---
name: directory-layout
description: On-disk layout for workspace/<topic>/ artifacts, fabric_notebooks/ build intermediates, and semantic-model TMDL.
kind: content
links:
  - graph-content/workflow/notebook-workflow
  - graph-content/semantic/semantic-models
---

# Directory layout

```text
workspace/
  <topic>/
    <name>.py            <- transient working source (# %% cells); removed after successful fetch
    <name>.Notebook/     <- canonical git artifact; ready for human commit after every passing run,
                           synced with Fabric UI via Git integration
    semantic-model/      <- TMDL definitions for any Power BI semantic model exposing topic tables
      <model>.tmdl       <- table + measure definitions (source of truth)
      README.md          <- UI creation walkthrough

fabric_notebooks/        <- build intermediates (gitignored), do not commit
  <topic>/
    <name>.Notebook/     <- built by build.py, consumed by deploy.py REST upload
```

Use one topic subfolder per data source or business domain, for example `workspace/lux_energy_price/`. Notebook stems must be unique across all subfolders because Fabric display names are flat.
