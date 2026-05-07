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

        D["🛠 developer\nworkspace/*.py with # %% cells\nbuild → fab import → fab job run → nbmon\nReports to orchestrator only\nTools: Read Write Edit Bash Glob Grep"]

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
    O -->|"tester FAIL RI/schema → route back to developer"| D
    O -->|"tester FAIL + PII · operator APPROVED → route"| P
    O -->|"operator BLOCKED → route to developer"| D

    D -->|"fab import · fab job run"| FABRIC
    D -.->|"updates memory/"| M
    T -.->|"logs result"| M
    P -.->|"audit entry"| M
```

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
| Shared | `memory/`, placeholder `.env.example`, `.gitignore` block, `workspace/`, `data/sandbox/`, `contracts/`, `runbooks/`, selected `bin/` tooling |

Profiles own their own instructions, skills, agents, and settings. The only shared runtime state is `memory/`.

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

The developer never uses the Fabric portal to edit notebooks. All changes happen in local `.py` files and are pushed via CLI.

```mermaid
sequenceDiagram
    actor Human
    participant Portal as Fabric Portal
    participant Dev as developer agent
    participant Build as build_fabric_notebooks.py
    participant Fab as fab CLI
    participant Nbmon as nbmon

    Human->>Portal: Create notebook item in sandbox workspace
    Human->>Dev: "notebook [name] is ready — workspace-id [id], item-id [id]"
    Dev->>Dev: Store IDs in memory/platform.md
    Dev->>Dev: Author / edit workspace/<name>.py using # %% cell markers

    loop 1–3 iterations until PASS
        Dev->>Build: uv run bin/build_fabric_notebooks.py
        Build-->>Dev: fabric_notebooks/<name>.Notebook

        Dev->>Fab: fab import fabric_notebooks/<name>.Notebook --workspace-id
        Fab-->>Dev: import OK

        Dev->>Fab: fab job run --item-id --workspace-id
        Fab-->>Dev: Run ID

        Dev->>Nbmon: nbmon status <run-id>
        Note over Nbmon: Cold start: ~3 min F64, up to 12 min F2/F4
        Nbmon-->>Dev: STATUS · CATEGORY · TRACEBACK · ADVISE · CELL

        alt FAIL
            Dev->>Dev: Fix the failing cell only — rebuild and redeploy
        end
    end

    Dev->>Dev: Update memory/project.md → handoff to tester
```

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

## Safety behavior

`bin/install-fabric-agent` requires a git target, refuses to install into this source repo unless `--self-test` is passed, protects unmanaged files by default, supports `--backup`, and merges a managed `.gitignore` block idempotently.

## Validation

```bash
uv run bin/validate-install-package.py
uv run bin/validate-agent-guidance.py
```

For installer changes, also run a disposable-target smoke test:

```bash
tmp=$(mktemp -d)
git init -q "$tmp"
./bin/install-fabric-agent --profile all --target "$tmp" --dry-run
./bin/install-fabric-agent --profile all --target "$tmp"
./bin/install-fabric-agent --profile all --target "$tmp" --check
```

