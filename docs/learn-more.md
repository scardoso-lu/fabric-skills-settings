# Learn more: Fabric Agent Pack architecture and operating model

This guide contains the extra context that used to make the README long. It separates what humans need to understand from what agents and automation need to follow.

## Human view

Humans use this repository to install an agent profile into a separate Fabric project repository. After installation, humans should work in the target repository and ask Codex or Claude Code to perform Fabric data engineering tasks there.

Human responsibilities:

- Choose the target repository and install the desired profile.
- Provide or approve Fabric workspace configuration.
- Prefer service-principal credentials for auditable agent activity.
- Review failed or unclear Fabric runs before another execution is attempted.
- Review security, data-quality, and release handoffs before production use.

## Machine view

Agents and automation treat the installed target repository as the runtime workspace.

Machine responsibilities:

- Read `memory/` at session start and update it when project state changes.
- Keep implementation, testing, and security-review roles separate.
- Author Fabric notebook source as local `.py` files with `# %%` cell markers.
- Build notebook bundles before deployment.
- Deploy notebooks through the Fabric REST API helper, not by editing notebooks in the Fabric portal.
- Smoke-test existing deployed notebooks as a separate step from deployment.
- Preserve data-quality, lineage, and security checks as explicit workflow gates.

## How it works

```mermaid
flowchart TD
    H(["👤 Human"])

    subgraph Source["fabric-skills-settings  —  this repo"]
        INST["🔧 install-fabric-agent\nprofile installer"]
    end

    subgraph Target["Target Repo  —  runtime workspace"]
        O["🎯 orchestrator\nCentral hub · reads memory/ first\nRoutes all work · receives all results\nNever implements · never writes code\nTools: Read Glob Grep"]

        D["🛠 developer\nworkspace/*.py with # %% cells\ntool/notebook/build.py → deploy.py → monitor\nReports to orchestrator only\nTools: Read Write Edit Bash Glob Grep"]

        T["🔍 tester\nValidates independently · Great Expectations per layer\nNull PKs · dupes · schema drift · RI · PII · lineage\nReports to orchestrator only\nTools: Read Bash Glob Grep"]

        P["🔒 operator\nRead-only security review · never modifies code\nSecrets · masking · least-privilege · RLS/OLS\nReports to orchestrator only\nTools: Read Bash Glob Grep"]

        M[("💾 memory/\nMEMORY.md · notebook-authoring.md\nRTK.md · <topic>/project.md")]
    end

    FABRIC["☁️ Fabric Workspace\nsandbox only"]

    H -->|"install profiles"| INST
    INST -->|"CLAUDE.md · AGENTS.md · skills/ · agents/"| Target

    H -->|"request"| O
    O -.->|"reads at session start"| M

    O -->|"build · implement · fix · migrate"| D
    O -->|"test · validate · DQ · anomaly"| T
    O -->|"secrets · PII · access · prod handoff"| P

    D -->|"done → report to orchestrator"| O
    D -->|"blocked on secrets/PII → report to orchestrator"| O
    T -->|"PASS → report to orchestrator"| O
    T -->|"FAIL → report to orchestrator"| O
    P -->|"APPROVED → report to orchestrator"| O
    P -->|"BLOCKED + remediation → report to orchestrator"| O

    O -->|"developer done → route to tester"| T
    O -->|"tester FAIL RI/schema → notify human · await approval → developer"| D
    O -->|"tester FAIL + PII · operator APPROVED → route"| P
    O -->|"operator BLOCKED → route to developer"| D

    D -->|"tool/notebook/deploy.py (Fabric REST API)"| FABRIC
    D -.->|"updates memory/"| M
    T -.->|"logs result"| M
    P -.->|"audit entry"| M
```

## Target repository `tool/` layout

The Shared profile installs five tool groups into every target repository:

| Directory | Who runs it | Purpose |
|---|---|---|
| `tool/setup/` | Human, one-time | Environment setup and Fabric admin helpers: `setup.ps1`, `setup.sh`, `fab-sandbox`, `fabric-inventory-readonly` |
| `tool/notebook/` | Developer agent | Notebook build → deploy → smoke-test cycle: `build.py`, `deploy.py`, `smoke-test.ps1/sh` |
| `tool/lakehouse/` | Developer agent | `list-tables.py` — read-only inventory of lakehouse tables with column names and types |
| `tool/pipeline/` | Developer agent | `manage.py` — create, deploy, run, and monitor a Data Factory pipeline that chains all topic notebooks |
| `tool/validate/` | Developer agent | Pre-deploy gates: `pipeline-lineage.py` for staging path consistency and `source-contract.py` for contract YAML shape |
| `tool/mcp/` | Infrastructure | MCP server exposing Fabric CLI commands to agents |
| `tool/pre-commit-check.ps1/sh` | Developer agent | Runs validators before committing workspace changes |

## Notebook deploy loop

The developer never uses the Fabric portal to edit notebooks. All changes happen in local `.py` files and are deployed through the Fabric REST API. Deploy and smoke test are separate steps; the smoke test never deploys.

```mermaid
sequenceDiagram
    actor Human
    participant Dev as developer agent
    participant Build as tool/notebook/build.py
    participant Deploy as tool/notebook/deploy.py
    participant Smoke as smoke-test.ps1 / smoke-test.sh

    Note over Human: One-time setup (workstation)
    Human->>Human: Set FABRIC_WORKSPACE_ID in .env
    Human->>Human: fab-sandbox auth login
    Note over Human: Per-task
    Human->>Dev: "build notebook [name]"
    Dev->>Dev: Author / edit workspace/<topic>/<name>.py using # %% cell markers

    Note over Dev,Deploy: Deploy once per source change
    Dev->>Build: python tool/notebook/build.py
    Build-->>Dev: fabric_notebooks/<topic>/<name>.Notebook

    Dev->>Deploy: python tool/notebook/deploy.py deploy <name> <workspace_id>
    Deploy-->>Dev: create/update OK (notebook created in Fabric if new)

    Note over Dev,Smoke: Smoke test — triggers existing notebook, never deploys
    Dev->>Smoke: Windows: tool\notebook\smoke-test.ps1 -Notebook <name><br/>Linux/Mac: tool/notebook/smoke-test.sh --notebook <name>
    Smoke->>Deploy: deploy.py exec <name> <workspace_id>
    Deploy-->>Smoke: job triggered · polling…
    Note over Deploy: Cold start: ~3 min F64, up to 12 min F2/F4
    Deploy-->>Smoke: STATUS: Completed / Failed / Cancelled

    alt STATUS: Completed
        Dev->>Deploy: deploy.py fetch <name> <workspace_id>
        Note over Dev: Report fetch complete to orchestrator. STOP.<br/>Human commits via Fabric UI Git integration.
    else STATUS: Failed or unclear
        Dev->>Human: Report FAIL + failureReason · await approval
        Human-->>Dev: Approve next run
        Dev->>Dev: Fix failing cell · redeploy · re-run smoke test
    end
```

`fab import` and `fab job run` require an interactive Windows console and fail in Git Bash or sandboxed environments. `tool/notebook/deploy.py` uses `fab api` calls through the CLI, which works across supported environments. On Windows it routes through `tool/setup/fab-sandbox.ps1` to keep the authenticated `fab` profile isolated. It also enables `_inlineInstallationEnabled` on triggered runs so `%pip install` cells work when a notebook starts through the API.

## Medallion pipeline flow

DQ notebooks are always separate files from ingestion notebooks. The tester validates each layer independently using Great Expectations.

```mermaid
flowchart LR
    SRC["📄 Source\nCSV · API · DB\ndata/sandbox/"]

    subgraph Dev["Developer builds  (notebook-loop per layer)"]
        B["🥉 bronze_src.py\nraw · append-only\n_ingest_timestamp\n_source_system · _batch_id"]
        S["🥈 silver_src.py\ncleaned · typed\nDelta MERGE · deduped"]
        G["🥇 gold_model.py\nfacts · dims · KPIs\nsemantic model"]
    end

    subgraph Test["Tester validates  (independently · Great Expectations)"]
        BQ["dq_bronze_src.py\nnull PKs · row count\nlineage envelope\nschema vs contract"]
        SQ["dq_silver_src.py\nduplicates · type checks\nrow count delta ≤20%"]
        GQ["dq_gold_model.py\nRI · metric sanity\nPII masking · RLS"]
    end

    PASS(["✅ PASS → orchestrator"])
    ESC_D(["🔁 → developer\nRI · schema drift"])
    ESC_O(["🚨 → operator\nDQ FAIL + PII suspicion"])

    SRC --> B
    B --> BQ
    BQ -->|pass| S
    S --> SQ
    SQ -->|pass| G
    G --> GQ
    GQ -->|all pass| PASS

    BQ -->|fail| ESC_D
    SQ -->|fail| ESC_D
    GQ -->|RI · schema| ESC_D
    GQ -->|DQ FAIL + PII| ESC_O
```

## Fabric notebook authoring rules

These rules apply inside every `workspace/<topic>/*.py` notebook source file:

| Rule | Correct | Wrong |
|---|---|---|
| Lakehouse paths | `Files/data/sandbox/topic/file.csv` | `/lakehouse/default/Files/...` |
| Non-standard packages | `%pip install "pkg>=x,<y"` as first cell | Import at top when runtime lacks package |
| Pipeline path alignment | Shared `FABRIC_STAGING_DIR` constant; run `python tool/validate/pipeline-lineage.py` before build | Hard-coded or mismatched strings |
| Fabric vs local portability | `mssparkutils` detection and relative fallback | Hard Fabric assumption |

## Safety behavior

`bin/install-fabric-agent` requires a git target, refuses to install into this source repo unless `--self-test` is passed, protects unmanaged files by default, supports `--backup`, and merges a managed `.gitignore` block idempotently.

## Validation commands

Run these from this source package repository. They validate the installer package and profile guidance; they are not installed into target repositories.

```bash
python3 bin/validate-install-package.py
python3 bin/validate-agent-guidance.py
```

To check that an installed target repository is still aligned with this package, run the installer check from this source repository:

```bash
python3 bin/install-fabric-agent --profile all --target /path/to/project-repo --check
```

For installer changes, also run a disposable-target smoke test:

```bash
tmp=$(mktemp -d)
git init -q "$tmp"
./bin/install-fabric-agent --profile all --target "$tmp" --dry-run
./bin/install-fabric-agent --profile all --target "$tmp"
./bin/install-fabric-agent --profile all --target "$tmp" --check
```
