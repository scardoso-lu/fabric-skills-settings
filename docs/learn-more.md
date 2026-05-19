# Learn More: Fabric Agent Pack

Fabric Agent Pack is a starter system for building Microsoft Fabric data projects with Codex or Claude Code. It gives a normal git repository the working shape of a Fabric project: profile guidance, role-specific agents, skills, memory, setup scripts, notebook deployment tools, validation helpers, and pipeline automation.

The main idea is simple: humans own the project, credentials, approvals, and production decisions; agents work inside the target repository and use repo-owned tools to build, deploy, validate, and report.

## The Shape

This repository is the package. A target repository is the actual Fabric project.

```mermaid
flowchart LR
    Source["fabric-skills-settings<br/>source package"]
    Installer["bin/install-fabric-agent"]
    Target["target git repository<br/>runtime workspace"]
    Fabric["Microsoft Fabric<br/>workspace"]
    Human["human maintainer"]
    Agent["Codex or Claude Code"]
    Mock["tool/data/mock-data-generator.py<br/>optional synthetic source data"]

    Source --> Installer
    Installer -->|installs profiles, skills, memory, tools| Target
    Human -->|runs setup and approves work| Target
    Agent -->|works from repo root| Target
    Agent -->|generates sandbox data when no source exists| Mock
    Mock --> Target
    Target -->|deploys notebooks and pipelines via tool/| Fabric
    Fabric -->|run results and fetched definitions| Target
```

The package installs two kinds of things:

| Installed asset | Why it matters |
|---|---|
| `AGENTS.md` / `CLAUDE.md` | Tells the agent how to behave in a Fabric project. |
| `.agents/skills` or `.claude/skills` | Gives task-specific playbooks for ingestion, validation, operations, modeling, mock data, and semantic model inspection. |
| `memory/` | Keeps project state, installed rules, and lessons available across sessions. |
| `tool/setup/` | Helps humans configure local Fabric access safely. |
| `tool/data/` | Generates deterministic synthetic sandbox files when a topic needs mock source data. Schema-driven; always pass `--schema` or `--schema-file`. |
| `tool/notebook/` | Builds, deploys, runs, monitors, and fetches notebooks. |
| `tool/pipeline/` | Creates and runs Data Factory pipelines from deployed notebooks. |
| `tool/lakehouse/` | Lists lakehouse tables and column schemas so agents can inspect the target table before authoring notebooks or generating mock data. |
| `tool/semantic-model/` | Lists and inspects Fabric Semantic Models — tables, DAX measures, relationships — before writing DAX queries or mapping Gold-layer outputs to KPIs. |
| `tool/validate/` | Catches staging-path and lineage mistakes before deploy. |
| `tool/mcp/` | Gives agents safe Fabric discovery through MCP. |

Skill source files live once under `profiles/skills/` in this package. During installation, that same source tree is copied to `.agents/skills/` for Codex, `.claude/skills/` for Claude, or both when `--profile all` is used. Rule source files live under `rules/` and are installed as `memory/rules/` so every agent reads the same DE/FP/SEC rule corpus through `memory/MEMORY.md`.

## Why This Pattern

Fabric projects are easy to make inconsistent when notebook edits happen partly in the portal, partly in local files, and partly through one-off commands. This pack makes the repository the working center:

- Local notebook sources are edited in `workspace/<topic>/`.
- Build artifacts go to `fabric_notebooks/` and are not committed.
- Fabric is updated through `tool/notebook/deploy.py`.
- Passing Fabric definitions are fetched back into `workspace/<topic>/<name>.Notebook/`.
- Humans review and commit through the normal project process.

That gives new contributors a visible path from source code to Fabric run result, instead of a scattered set of portal actions.

## Human And Agent Roles

Humans create the Fabric workspace, service principal, lakehouses, warehouses, and production approvals. Agents do the repo-local engineering work and stop when they need human judgment.

```mermaid
flowchart TD
    Human["Human<br/>owns access, approvals, production"]
    Orchestrator["Orchestrator<br/>scopes and routes"]
    Developer["Developer<br/>builds notebooks and pipelines"]
    Tester["Tester<br/>validates data quality"]
    Operator["Operator<br/>reviews security and handoff"]
    Memory["memory/<br/>project state"]
    Tools["tool/<br/>repo-owned automation"]
    Fabric["Fabric workspace"]

    Human --> Orchestrator
    Orchestrator --> Memory
    Orchestrator --> Developer
    Orchestrator --> Tester
    Orchestrator --> Operator
    Developer --> Tools
    Tester --> Tools
    Operator --> Tools
    Tools --> Fabric
    Fabric --> Tools
    Tools --> Memory
    Orchestrator --> Human
```

The practical rule is: agents can create and update notebooks, workspace folders, and development pipelines through the installed tools. Humans own credentials, secrets, lakehouse and warehouse creation, production promotion, and git handoff.

## Setup In A Target Repo

After installing the profile, the human runs one setup command from the target repository:

```powershell
.\tool\setup\setup.ps1
```

```bash
bash tool/setup/setup.sh
```

Setup checks local tools, installs `ms-fabric-cli` if needed, initializes RTK when possible, creates `.venv`, installs Faker, Mimesis, scikit-learn, semantic-link, and pandas into that venv, prompts for Fabric service-principal settings, verifies that Fabric API access works, and refreshes `workspaces.json`.

| Value | Stored where |
|---|---|
| `FABRIC_TENANT_ID` | `.env` |
| `FABRIC_CLIENT_ID` | `.env` |
| `FABRIC_CLIENT_SECRET` | OS user environment, never `.env` |

Workspace and resource IDs come from `workspaces.json`. Use `python tool/workspace/switch.py list` and `python tool/workspace/switch.py <displayName>` to write the selected workspace into the auto-generated `.env` block.

Agents should not inspect secrets. Runtime helpers load `.env` inside their own process when they need configuration.

## Notebook Loop

The notebook loop is the core workflow.

```mermaid
sequenceDiagram
    actor Human
    participant Agent as Agent
    participant Source as workspace/<topic>/<name>.py
    participant Build as tool/notebook/build.py
    participant Deploy as tool/notebook/deploy.py
    participant Fabric as Fabric
    participant Fetched as workspace/<topic>/<name>.Notebook

    Human->>Agent: Request a notebook or fix
    Agent->>Source: Edit local # %% source
    Agent->>Build: Build .Notebook bundle
    Agent->>Deploy: Deploy through Fabric REST API
    Deploy->>Fabric: Create or update notebook
    Agent->>Deploy: Smoke test existing deployed notebook
    Deploy->>Fabric: Trigger and monitor run
    alt Run passes
        Agent->>Deploy: Fetch Fabric definition
        Deploy->>Fetched: Update fetched .Notebook files
        Agent-->>Human: Report result and handoff
    else Run fails
        Agent-->>Human: Report failure and wait before rerun
    end
```

The commands are intentionally boring:

```bash
# Generate mock data — --schema is always required
python tool/data/mock-data-generator.py --schema '[{"name":"id","type":"id"},{"name":"amount","type":"decimal"}]' --topic orders --rows 1000
python tool/data/mock-data-generator.py --engine faker --schema '[{"name":"id","type":"id"},{"name":"email","type":"email"}]' --topic customers --rows 1000
python tool/data/mock-data-generator.py --engine mimesis --schema-file schemas/<topic>.json --rows 5000
python tool/data/mock-data-generator.py --engine sklearn --schema '[{"name":"price","type":"float"},{"name":"qty","type":"float"},{"name":"target","type":"int"}]' --rows 5000

# Inspect lakehouse and semantic model
python tool/lakehouse/list-tables.py
python tool/semantic-model/inspect.py list
python tool/semantic-model/inspect.py show <model-name-or-id>
python tool/semantic-model/inspect.py show <model-name-or-id> --json

# Validate, build, deploy
python tool/validate/pipeline-lineage.py
python tool/notebook/build.py
python tool/notebook/deploy.py deploy <name> <workspace_id>
python tool/notebook/deploy.py fetch <name> <workspace_id>
```

Smoke tests trigger what is already deployed; they do not deploy:

```powershell
powershell -ExecutionPolicy Bypass -File tool/notebook/smoke-test.ps1 -Notebook <name>
```

```bash
bash tool/notebook/smoke-test.sh --notebook <name>
```

## Medallion Pipeline Flow

A good Fabric topic is easy to reason about because each notebook has one job. Downloaders stage raw files. Bronze notebooks ingest. DQ notebooks validate. Silver and Gold notebooks transform and model. The tester validates each layer independently using Great Expectations.

```mermaid
flowchart LR
    SRC["Source<br/>CSV · API · DB<br/>data/sandbox/"]
    MOCK["tool/data/mock-data-generator.py<br/>optional synthetic CSV<br/>for new or demo topics"]

    subgraph Dev["Developer builds  (notebook loop per layer)"]
        D["download_&lt;source&gt;.py<br/>fetch raw source files<br/>skip files already staged"]
        B["bronze_&lt;source&gt;.py<br/>raw · append-only<br/>_ingest_timestamp<br/>_source_system · _batch_id"]
        S["silver_&lt;source&gt;.py<br/>cleaned · typed<br/>Delta MERGE · deduped"]
        G["gold_&lt;model&gt;.py<br/>facts · dims · KPIs<br/>semantic model"]
    end

    subgraph Test["Tester validates  (independently · Great Expectations)"]
        BQ["dq_bronze_&lt;source&gt;.py<br/>null PKs · row count<br/>lineage envelope<br/>schema vs contract"]
        SQ["dq_silver_&lt;source&gt;.py<br/>duplicates · type checks<br/>row count delta &lt;=20%"]
        GQ["dq_gold_&lt;model&gt;.py<br/>RI · metric sanity<br/>PII masking · RLS"]
    end

    PIPE["pipeline_&lt;topic&gt;<br/>tool/pipeline/manage.py<br/>download -> bronze -> dq_bronze -> silver -> dq_silver -> gold -> dq_gold"]
    PASS(["PASS -> orchestrator"])
    ESC_D(["-> developer<br/>RI · schema drift"])
    ESC_O(["-> operator<br/>DQ FAIL + PII suspicion"])

    MOCK --> SRC
    SRC --> D
    D --> B
    B --> BQ
    BQ -->|pass| S
    S --> SQ
    SQ -->|pass| G
    G --> GQ
    GQ -->|all pass| PIPE
    PIPE --> PASS

    BQ -->|fail| ESC_D
    SQ -->|fail| ESC_D
    GQ -->|RI · schema| ESC_D
    GQ -->|DQ FAIL + PII| ESC_O
```

For a Bronze-only topic, start with three notebooks:

| Notebook | Purpose |
|---|---|
| `download_<source>.py` | Fetch raw source files and skip files already staged. |
| `bronze_<source>.py` | Process only new staged files and write the Bronze table. |
| `dq_bronze_<source>.py` | Run independent checks and fail loudly on bad data. |

This split keeps failures understandable. If a source API changes, fix the downloader. If table logic breaks, fix Bronze. If quality rules fail, inspect DQ output before rerunning.

## Pipeline Flow

Once notebooks are deployed, `tool/pipeline/manage.py` can chain them into a Fabric Data Factory pipeline.

```mermaid
flowchart TD
    Notebooks["deployed notebooks<br/>matching topic"]
    Params["pipeline_params.json<br/>plus --params overrides"]
    Manage["tool/pipeline/manage.py"]
    Pipeline["pipeline_<topic>"]
    Run["pipeline run"]
    Result{"result"}
    Pass["report pass"]
    Fail["report failure and stop"]

    Notebooks --> Manage
    Params --> Manage
    Manage -->|create or update| Pipeline
    Pipeline -->|run| Run
    Run --> Result
    Result -->|Completed| Pass
    Result -->|Failed, Cancelled, Deduped| Fail
```

Common commands:

```bash
python tool/pipeline/manage.py create --topic <topic>
python tool/pipeline/manage.py test --topic <topic>
python tool/pipeline/manage.py status --pipeline pipeline_<topic> --instance <job-instance-id>
python tool/pipeline/manage.py list
```

Auto-discovery orders notebooks by familiar prefixes:

```text
download_ -> bronze_ -> dq_bronze_ -> silver_ -> dq_silver_ -> gold_ -> dq_gold_
```

Use `--notebooks name1,name2` when a topic needs a custom order.

## Authoring Rules Worth Remembering

| Need | Use |
|---|---|
| Python kernel | `# FABRIC_KERNEL: python` |
| Lakehouse attachment | `# FABRIC_LAKEHOUSE: bronze` |
| Warehouse attachment | `# FABRIC_WAREHOUSE: data_warehouse` |
| Lakehouse file path | `Files/data/sandbox/topic/file.csv` |
| Runtime package | `%pip install "pkg>=x,<y"` before import |
| Pipeline parameters | `# %% [parameters]` cells |

Avoid portal-only notebook edits, hard-coded `/lakehouse/default/Files/...` paths, committed `.env` files, committed `fabric_notebooks/` bundles, and combined download-plus-ingest notebooks.

## Maintainer Checks

When changing this source package, run:

```bash
uv run bin/validate-install-package.py
uv run bin/validate-agent-guidance.py
uv run --group dev pytest
```

When changing installer mappings or profile files, also check a disposable target repository:

```bash
tmp=$(mktemp -d)
git init -q "$tmp"
python bin/install-fabric-agent --profile all --target "$tmp" --dry-run
python bin/install-fabric-agent --profile all --target "$tmp"
python bin/install-fabric-agent --profile all --target "$tmp" --check
```

## Deep Dive For Techs

This is the full operating model that sits behind the quick diagrams above.

```mermaid
flowchart TD
    H(["Human"])

    subgraph Source["fabric-skills-settings - source package"]
        INST["bin/install-fabric-agent<br/>profile installer"]
        V["bin/ validators<br/>validate-install-package.py<br/>validate-agent-guidance.py<br/>pytest"]
        MIRROR["tool/ source mirror<br/>kept aligned with<br/>profiles/shared/project-layout/tool/"]
    end

    subgraph Target["Target repo - runtime workspace"]
        O["orchestrator<br/>central hub<br/>reads memory first<br/>routes work and receives results<br/>never implements"]

        D["developer<br/>workspace/&lt;topic&gt;/*.py with # %% cells<br/>build -> deploy -> smoke test -> fetch<br/>pipeline create/run after notebook smoke tests"]

        T["tester<br/>independent Great Expectations validation<br/>row counts · null PKs · duplicates<br/>schema drift · RI · metric sanity · PII masking"]

        P["operator<br/>security and production handoff review<br/>secrets · PII · least privilege · RLS/OLS<br/>never modifies code"]

        M[("memory/<br/>MEMORY.md<br/>rules/*.md<br/>project.md<br/>&lt;topic&gt;/project.md<br/>sbom.md")]

        SETUP["tool/setup/<br/>setup.ps1 · setup.sh<br/>fab-sandbox<br/>fabric-inventory-readonly"]
        DATA["tool/data/<br/>mock-data-generator.py<br/>--schema required"]
        NOTEBOOK["tool/notebook/<br/>build.py<br/>deploy.py deploy / exec / run / fetch / monitor<br/>smoke-test.ps1/sh"]
        PIPELINE["tool/pipeline/<br/>manage.py<br/>create · run · status · list · test"]
        VALIDATE["tool/validate/<br/>pipeline-lineage.py"]
        LAKEHOUSE["tool/lakehouse/<br/>list-tables.py"]
        SEMMODEL["tool/semantic-model/<br/>inspect.py<br/>list · show · --json"]
        MCP["tool/mcp/<br/>Fabric MCP discovery"]
    end

    subgraph Fabric["Microsoft Fabric workspace - sandbox by default"]
        WS["Workspace<br/>created by human"]
        LH["Lakehouses and warehouses<br/>created by human"]
        NB["Notebook items<br/>created or updated by deploy.py"]
        DF["Data Factory pipeline<br/>created or updated by manage.py"]
        RUN["Runs and monitor results"]
    end

    H -->|"installs profile into target repo"| INST
    INST -->|"AGENTS.md · CLAUDE.md · skills · agents · memory · tool/"| Target
    MIRROR --> INST
    V -->|"package and guidance checks"| INST

    H -->|"runs setup and approves reruns or handoffs"| SETUP
    SETUP -->|"authenticates Fabric CLI profile"| WS
    H -->|"request"| O
    O -.->|"reads and updates through routed work"| M

    O -->|"build · implement · fix · migrate"| D
    O -->|"test · validate · DQ · anomaly"| T
    O -->|"secrets · PII · access · production handoff"| P

    D --> VALIDATE
    D --> DATA
    D --> LAKEHOUSE
    D --> SEMMODEL
    D --> NOTEBOOK
    D --> PIPELINE
    T --> LAKEHOUSE
    T --> SEMMODEL
    T --> NOTEBOOK
    P --> MCP
    P --> SETUP

    DATA -->|"writes synthetic CSV under data/sandbox/"| D
    NOTEBOOK -->|"build local .Notebook bundle"| D
    NOTEBOOK -->|"deploy via Fabric REST API"| NB
    NOTEBOOK -->|"exec and monitor"| RUN
    NOTEBOOK -->|"fetch passing Fabric definition"| Target
    PIPELINE -->|"chains deployed notebooks by topic order"| DF
    DF --> RUN
    NB --> RUN
    LH --> NB

    D -->|"complete or blocked report"| O
    T -->|"PASS or FAIL report"| O
    P -->|"APPROVED or BLOCKED report"| O

    O -->|"developer complete -> tester"| T
    O -->|"tester FAIL: RI or schema drift -> human approval -> developer"| D
    O -->|"tester FAIL with PII suspicion -> operator"| P
    O -->|"operator BLOCKED -> developer with remediation"| D
    O -->|"final status and handoff"| H
```
