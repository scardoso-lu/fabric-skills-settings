# Fabric Agent Pack

Vendor-native Codex and Claude Code profiles for Microsoft Fabric data engineering.

This repository is an installer/source package. It should not be used as the day-to-day Fabric project workspace. Install one or both profiles into the actual project repository, then open Codex or Claude Code from that target repository root.

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

        M[("💾 memory/\nMEMORY.md · project.md\nplatform.md · decisions.md")]
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

## Example run

The screenshots below are from an end-to-end bronze ingestion of EU day-ahead electricity prices into a Fabric Lakehouse.

**1 — Authoring the bronze notebook**

The developer agent authors `bronze_electricity_day_ahead_prices.py` in VS Code while the upstream `download_sources` job runs in parallel on the Fabric workspace.

![Claude Code authoring the bronze notebook source file alongside the Fabric Monitor showing download_sources in progress](img/fabric-0.png)

**2 — Deploying and triggering**

Codex reads the workspace ID from `.env`, deploys the notebook via the Fabric REST API, and triggers the run. The Monitor shows `bronze_electricity_day_ahead_prices` queued as "Not started".

![Codex terminal deploying the notebook while the Fabric Monitor shows the job queued](img/fabric-1.png)

**3 — Full run history**

The Monitor activity log after a complete iteration: `download_sources` → `bronze_electricity_day_ahead_prices` → `dq_bronze_electricity_day_ahead_prices` all succeed. Earlier DQ failures (visible in the log) reflect the agent iterating on the schema contract before reaching a green run.

![Fabric Monitor showing the full activity history with final succeeded runs and earlier failed DQ iterations](img/fabric-2.png)

**4 — Ingested Delta table**

The resulting `bronze_electricity_day_ahead_prices` Delta table in the DATALAKE Lakehouse — 1 000 rows, 27 columns, including the lineage envelope columns (`_ingest_timestamp`, `_source_system`, `_batch_id`) written by the bronze notebook.

![Fabric Lakehouse table view showing the ingested bronze_electricity_day_ahead_prices Delta table with 1000 rows](img/fabric-3.png)

## Setup this source package

### Linux / macOS

```bash
./setup.sh                  # check tools and validate package
./setup.sh --install-tools  # also install uv if missing
```

### Windows (PowerShell)

```powershell
.\setup.ps1                  # check tools and validate package
.\setup.ps1 -InstallTools    # also install uv if missing
.\setup.ps1 -Help            # show usage
```

Both scripts check for Git and uv, create `memory/project.md` if absent, and run the package validators.

## Profiles

| Profile | Installs |
|---|---|
| Codex | `AGENTS.md`, `.agents/skills/*/SKILL.md`, `.codex/agents/*.toml`, `.codex/config.toml` |
| Claude | `CLAUDE.md`, `.claude/skills/*/SKILL.md`, `.claude/agents/*.md`, `.claude/settings.json` |
| Shared | `memory/`, placeholder `.env.example`, `.gitignore` block, `workspace/`, `data/sandbox/`, `contracts/`, `runbooks/`, `bin/` tooling |

Profiles own their own instructions, skills, agents, and settings. The only shared runtime state is `memory/`.

### Target repo `bin/` layout

The Shared profile installs four tool groups into every target repository:

| Directory | Who runs it | Purpose |
|---|---|---|
| `bin/setup/` | Human (one-time) | Environment setup and Fabric admin — `setup.ps1`, `setup.sh`, `fab-sandbox`, `fabric-inventory-readonly` |
| `bin/notebook/` | Developer agent | Notebook build → deploy → smoke-test cycle — `build.py`, `deploy.py`, `smoke-test.ps1/sh` |
| `bin/validate/` | Developer agent | Pre-deploy gates — `pipeline-lineage.py` (staging path consistency), `source-contract.py` (contracts/ YAML shape) |
| `bin/mcp/` | Infrastructure | MCP server that exposes Fabric CLI commands to agents |

## Install into a target repository

```bash
# preview changes first
./bin/install-fabric-agent --profile all --target /path/to/project-repo --dry-run

# apply
./bin/install-fabric-agent --profile all --target /path/to/project-repo
```

Then work from the target repository:

```bash
cd /path/to/project-repo
codex   # or: claude
```

## Notebook deploy loop

The developer never uses the Fabric portal to edit notebooks. All changes happen in local `.py` files and are deployed via the Fabric REST API. Deploy and smoke test are **separate steps** — the smoke test never deploys.

```mermaid
sequenceDiagram
    actor Human
    participant Portal as Fabric Portal
    participant Dev as developer agent
    participant Build as tool/notebook/build.py
    participant Deploy as tool/notebook/deploy.py
    participant Smoke as smoke-test.ps1 / smoke-test.sh

    Human->>Portal: Create notebook item in sandbox workspace
    Human->>Dev: "notebook [name], set FABRIC_WORKSPACE_ID in .env"
    Dev->>Dev: Author / edit workspace/<name>.py using # %% cell markers

    Note over Dev,Deploy: Deploy once per source change
    Dev->>Build: python tool/notebook/build.py
    Build-->>Dev: fabric_notebooks/<name>.Notebook

    Dev->>Deploy: python tool/notebook/deploy.py deploy <name> <workspace_id>
    Deploy-->>Dev: create/update OK

    Note over Dev,Smoke: Smoke test — triggers existing notebook, never deploys
    Dev->>Smoke: Windows: tool\notebook\smoke-test.ps1 -Notebook <name><br/>Linux/Mac: tool/notebook/smoke-test.sh --notebook <name>
    Smoke->>Deploy: deploy.py exec <name> <workspace_id>
    Deploy-->>Smoke: job triggered · polling…
    Note over Deploy: Cold start: ~3 min F64, up to 12 min F2/F4
    Deploy-->>Smoke: STATUS: Completed / Failed / Cancelled

    alt STATUS: Completed
        Dev->>Deploy: deploy.py fetch <name> <workspace_id>
        Dev->>Dev: git commit workspace/<name>.Notebook/ · handoff to tester
    else STATUS: Failed or unclear
        Dev->>Human: Report FAIL + failureReason · await approval
        Human-->>Dev: Approve next run
        Dev->>Dev: Fix failing cell · redeploy · re-run smoke test
    end
```

> `fab import` and `fab job run` require an interactive Windows console and fail in Git Bash or sandboxed environments. `tool/notebook/deploy.py` uses `fab api` (REST API calls via CLI) which works everywhere. On Windows it automatically routes through `tool/setup/fab-sandbox.ps1` to keep the authenticated `fab` profile isolated. It also enables `_inlineInstallationEnabled` on every triggered run so `%pip install` cells work when a notebook is launched via the API.

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

These apply inside every `workspace/<topic>/*.py` notebook source file:

| Rule | Correct | Wrong |
|---|---|---|
| Lakehouse paths | `Files/data/sandbox/topic/file.csv` | `/lakehouse/default/Files/...` |
| Non-standard packages | `%pip install "pkg>=x,<y"` as first cell | import at top (runtime has only PySpark + stdlib) |
| Pipeline path alignment | shared `FABRIC_STAGING_DIR` constant; run `python tool/validate/pipeline-lineage.py` before build | hard-coded or mismatched strings |
| Fabric vs local portability | `mssparkutils` detection, relative fallback | `if True:` / hard Fabric assumption |

## Safety behavior

`bin/install-fabric-agent` requires a git target, refuses to install into this source repo unless `--self-test` is passed, protects unmanaged files by default, supports `--backup`, and merges a managed `.gitignore` block idempotently.

## Validation

Run these from this source package repository. They validate the installer package and profile guidance; they are not installed into target repositories.

```bash
uv run bin/validate-install-package.py
uv run bin/validate-agent-guidance.py
```

To check that an installed target repository is still aligned with this package, run the installer check from this source repository:

```bash
uv run python bin/install-fabric-agent --profile all --target /path/to/project-repo --check
```

For installer changes, also run a disposable-target smoke test:

```bash
tmp=$(mktemp -d)
git init -q "$tmp"
./bin/install-fabric-agent --profile all --target "$tmp" --dry-run
./bin/install-fabric-agent --profile all --target "$tmp"
./bin/install-fabric-agent --profile all --target "$tmp" --check
```
