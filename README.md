# Fabric Agent Pack

Vendor-native **Codex** and **Claude Code** profiles for Microsoft Fabric data engineering.

Fabric Agent Pack turns a normal git repository into a guided Microsoft Fabric project workspace. It installs agent instructions, specialized skills, setup scripts, validation tools, and notebook deployment helpers so humans can ask for Fabric data engineering work while agents follow a consistent, auditable workflow.

> This repository is the **source package and installer**, not the day-to-day Fabric project workspace. Install a profile into your actual project repository, then run Codex or Claude Code from that target repository root.

**Overview**

![Fabric Agent Pack](img/overview.png)

## Quick start

Both paths give you the same install — a single command, no two-step dance.

### Option A — pip install (recommended for users)

No git clone required. Install the package and run the CLI directly:

```bash
pip install fabric-skills-settings

# preview
install-fabric-agent --profile claude --target /path/to/project-repo --dry-run

# apply
install-fabric-agent --profile claude --target /path/to/project-repo
```

### Option B — from source (contributors)

Clone the repo and use the `setup.ps1` / `setup.sh` single-shot CLI. It runs the validators first, then installs.

#### Linux / macOS

```bash
git clone https://github.com/scardoso-lu/fabric-skills-settings && cd fabric-skills-settings

# preview
./setup.sh --profile claude --target /path/to/project-repo --dry-run

# apply
./setup.sh --profile claude --target /path/to/project-repo
```

#### Windows (PowerShell)

```powershell
git clone https://github.com/scardoso-lu/fabric-skills-settings; cd fabric-skills-settings

# preview
.\setup.ps1 -Profile claude -Target C:\path\to\project-repo -DryRun

# apply
.\setup.ps1 -Profile claude -Target C:\path\to\project-repo
```

### Common flags

| Flag (bash / PowerShell) | Effect |
|---|---|
| `--profile codex \| claude \| all` / `-Profile` | Pick the agent profile (required for install) |
| `--target <path>` / `-Target` | Target git repository (required for install) |
| `--dry-run` / `-DryRun` | Preview changes without writing (skips bootstrap) |
| `--check` / `-Check` | Verify target state, exit 1 if it drifts (skips bootstrap) |
| `--force` / `-Force` | Overwrite non-managed existing files |
| `--backup` / `-Backup` | Back up replaced files alongside the originals |
| `--no-bootstrap` / `-NoBootstrap` | Copy files only; skip the post-install `.venv` + Fabric auth + workspaces.json bootstrap |
| `--skip-validators` / `-SkipValidators` | Skip the pre-install validator pass (source-clone only) |
| `--install-tools` / `-InstallTools` | Auto-install `uv` if missing (source-clone wrappers only) |
| `--help` / `-Help` | Show usage |

### Service-principal credentials

Minimum Fabric workspace role: **Contributor**. The bootstrap prompts for these and stores them safely:

| Prompt | Stored where |
|---|---|
| `FABRIC_TENANT_ID` | `<target>/.env` |
| `FABRIC_CLIENT_ID` | `<target>/.env` |
| `FABRIC_CLIENT_SECRET` | OS environment only — never `.env` |

On Windows the secret is written to the user registry via `SetEnvironmentVariable("User")`. On Linux/macOS it is appended to your shell profile (`~/.zprofile`, `~/.bash_profile`, or `~/.profile`).

Create the service principal once, before running setup:

```text
Azure Portal → App registrations → New registration
  Name: fabric-agent-<project>
  Supported account types: this tenant only

Fabric workspace → Manage access → Add → service principal
  Role: Contributor
```

Re-running the same install command is idempotent — credentials already set are skipped, and managed files only change when their source content changes. If you need to bootstrap again later (e.g. after rotating the secret), run `<target>/tool/setup/setup.{ps1,sh}` directly from inside the target.


## Learn more

- [docs/workflow.md](docs/workflow.md) — agent → skill → tool → Fabric flow, focused on what you get in the target repo.
- [docs/knowledge-graph.md](docs/knowledge-graph.md) — what's indexed under `memory/` and the `graph_*` MCP surface the agents call.
- [docs/architecture.md](docs/architecture.md) — full source-vs-target picture: MCP servers, folder layout, setup CLI, and the redesign migration notes.


## Example result

The screenshots below show an end-to-end bronze ingestion of EU day-ahead electricity prices into a Fabric Lakehouse.

**1 — Authoring the bronze notebook**

The developer agent authors `bronze_electricity_day_ahead_prices.py` while the upstream `download_sources` job runs in Fabric.

![Claude Code authoring the bronze notebook source file alongside the Fabric Monitor showing download_sources in progress](img/fabric-0.png)

**2 — Deploying and triggering**

Codex reads the workspace ID from `.env`, deploys the notebook through the Fabric REST API, and triggers the run.

![Codex terminal deploying the notebook while the Fabric Monitor shows the job queued](img/fabric-1.png)

**3 — Full run history**

The Fabric Monitor shows `download_sources` → `bronze_electricity_day_ahead_prices` → `dq_bronze_electricity_day_ahead_prices` succeeding after schema-contract iterations.

![Fabric Monitor showing the full activity history with final succeeded runs and earlier failed DQ iterations](img/fabric-2.png)

**4 — Ingested Delta table**

The resulting Delta table contains 1,000 rows and 27 columns, including lineage envelope fields such as `_ingest_timestamp`, `_source_system`, and `_batch_id`.

![Fabric Lakehouse table view showing the ingested bronze_electricity_day_ahead_prices Delta table with 1000 rows](img/fabric-3.png)


**5 — Restricted workspace for AI agentic development**

The agent runs in a dedicated workspace. Permissions are set at the workspace level to ensure there is no access to production data or pipelines.

![Fabric Workspace permissions](img/fabric-4.png)

**6 — Development Lifecycle**

The code is integrated with Git, and the agent develops everything in a dedicated feature branch. Human developers can review the pull request later and merge the work from the feature branch into dev.

![Agent Feature branch](img/fabric-5.png)

> **Note**: The VIBECODING workspace was set up by selecting individual Fabric items. This narrowed down the codebase to only the scripts that stakeholders actually care about.

## Live reference implementation

[**fabric-open-data-lu**](https://github.com/scardoso-lu/fabric-open-data-lu) is a public target repository with Claude- and Codex-generated scripts for EU open-data ingestion into Microsoft Fabric. It demonstrates the `download_` → `bronze_` → `dq_bronze_` notebook pattern used by this package.

## Why use it?

- **Ship faster** — agents handle notebook authoring, deployment, schema validation, and pipeline wiring. Engineers own approvals and production handoffs.
- **OWASP-compliant by default** — Data Security Top 10 and Supply Chain (A03:2025) baked in: no credential leakage, parameterized queries, pinned dependencies, CVE checks, PII masking.
- **Harness engineering** — agents run inside a structured harness of guardrails, role definitions, skill boundaries, and memory. Consistent, auditable behavior without custom prompt engineering per project.
- **Separation of duties** — implementation, testing, and security review are distinct agents. Nothing reaches production without a human sign-off.
- **Quality gates at every layer** — mandatory Great Expectations checks at bronze, silver, and gold. Failed DQ stops the pipeline; agents do not auto-retry.
- **Token savings** — RTK optimizer cuts shell-output tokens 60–90%, keeping long sessions economical.
