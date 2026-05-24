# Fabric Agent Pack

Vendor-native **Codex** and **Claude Code** profiles for Microsoft Fabric data engineering.

Fabric Agent Pack turns a normal git repository into a guided Microsoft Fabric project workspace. It installs agent instructions, specialized skills, setup scripts, validation tools, and notebook deployment helpers so humans can ask for Fabric data engineering work while agents follow a consistent, auditable workflow.

> This repository is the **source package and installer**, not the day-to-day Fabric project workspace. Install a profile into your actual project repository, then run Codex or Claude Code from that target repository root.

**Overview**

![Fabric Agent Pack](img/overview.png)

## Quick start

### Option A — pip install (recommended)

No git clone required. Install the package and run the CLI directly:

```bash
pip install fabric-skills-settings
```

Preview what will be written, then apply:

```bash
# preview
uv run install-fabric-agent --profile claude --target /path/to/project-repo --dry-run

# apply
uv run install-fabric-agent --profile claude --target /path/to/project-repo
```

`--profile` accepts `claude`, `codex`, or `all`. The installer drops a minimal entrypoint (`CLAUDE.md` or `AGENTS.md`, ~30 lines) plus two MCP servers — `fabric` and `fabric-graph` — into the target repo. The first thing agents do in the target repo is call `graph_get_entry` to read the setup gate and traverse the knowledge graph.

After install, run `claude` or `codex` from the target repo root.

---

### Option B — from source (contributors)

Clone this repository, then prepare the source package:

#### Linux / macOS

```bash
./setup.sh                  # check tools and validate package
./setup.sh --install-tools  # also install uv if missing
```

#### Windows (PowerShell)

```powershell
.\setup.ps1                  # check tools and validate package
.\setup.ps1 -InstallTools    # also install uv if missing
.\setup.ps1 -Help            # show usage
```

Both setup scripts check for Git and uv and run the package validators.

Build the local knowledge graph artifact before using the `fabric-graph` MCP server from this source checkout. The build commands mirror the installer's `--target` / `--dry-run` flag style:

```bash
# preview — validate and print stats, no artifacts written
uv run --group dev python bin/build-graph.py --target . --dry-run --stats
uv run --group dev python bin/build-agent-capability-graph.py --target . --dry-run --stats

# apply — write memory/.graph/{graph.json, graph-bm25.pkl, materialized-graph.svg}
#              and agent-capabilities.{json,svg}
uv run --group dev python bin/build-graph.py --target . --stats
uv run --group dev python bin/build-agent-capability-graph.py --target . --stats
```

`--target` accepts any repo (this source checkout, an installed target, a disposable smoke-test directory). `--dry-run` runs the build pipeline in memory and prints findings without touching disk.

The source repo splits graph code into:

- `tool/graph/` — **runtime** modules used by the installed MCP server (schema, store, search, writes, builder, lock).
- `build/graph_build/` — **build-time-only** modules used by `bin/build-*.py` (visualize, agent_capabilities). Not installed into target repos.

Install into a target repository:

```bash
uv run install-fabric-agent --profile claude --target /path/to/project-repo --dry-run
uv run install-fabric-agent --profile claude --target /path/to/project-repo
```

Then work from the target repository:

```bash
cd /path/to/project-repo
codex   # or: claude
```

---

### 2. Configure Fabric access in the target repository

Minimum required Fabric workspace role: **Contributor**. Run the setup script to create the local `.venv`, install the Python helper libraries, authenticate Fabric access, and refresh the workspace registry. You do not need to edit `.env` manually.

```powershell
# Windows
.\tool\setup\setup.ps1
```
```bash
# Linux / macOS
bash tool/setup/setup.sh
```

The script prompts for service-principal credentials only:

| Prompt | Stored where |
|---|---|
| `FABRIC_TENANT_ID` | `.env` |
| `FABRIC_CLIENT_ID` | `.env` |
| `FABRIC_CLIENT_SECRET` | OS environment only — never `.env` |

On Windows the secret is written to the user registry via `SetEnvironmentVariable("User")`. On Linux/macOS it is appended to your shell profile (`~/.zprofile`, `~/.bash_profile`, or `~/.profile`).

Create the service principal before running setup:

```text
Azure Portal → App registrations → New registration
  Name: fabric-agent-<project>
  Supported account types: this tenant only

Fabric workspace → Manage access → Add → service principal
  Role: Contributor
```

Re-running setup is idempotent — values already set are skipped.

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

## Learn more

For architecture diagrams of the two MCP servers, the RAG knowledge graph, and the skills + tools each server exposes, see [docs/architecture.md](docs/architecture.md).

## Validation commands for contributors

Run these from this source package repository after changing profiles, installer logic, guidance, validation, or installable tooling:

```bash
uv run bin/validate-install-package.py
uv run bin/validate-agent-guidance.py
uv run --group dev pytest
```

For installer changes, also run a disposable-target smoke test:

```bash
tmp=$(mktemp -d)
git init -q "$tmp"
uv run install-fabric-agent --profile all --target "$tmp" --dry-run
uv run install-fabric-agent --profile all --target "$tmp"
uv run install-fabric-agent --profile all --target "$tmp" --check
```

## What gets installed?

| Profile | Installed into target repo |
|---|---|
| Codex | `AGENTS.md`, `.agents/skills/*/SKILL.md` copied from `profiles/skills/`, `.codex/agents/*.toml`, `.codex/config.toml` |
| Claude | `CLAUDE.md`, `.claude/skills/*/SKILL.md`, `.claude/agents/*.md`, `.claude/settings.local.json` |
| Shared | `memory/` including `memory/rules/` and `memory/graph-content/`, placeholder `.env.example`, managed `.gitignore` block, `workspace/`, `data/sandbox/`, `contracts/`, `tool/` (with `tool/mcp/` running the `fabric` and `fabric-graph` MCP servers) |


The only shared runtime state between vendor profiles is `memory/`. Runtime Codex assets stay under `profiles/codex/`; runtime Claude assets stay under `profiles/claude/`. Skill source is intentionally single-source under `profiles/skills/` and is copied to both runtime skill paths during installation.


## Why use it?

- **Ship faster** — agents handle notebook authoring, deployment, schema validation, and pipeline wiring. Engineers own approvals and production handoffs.
- **OWASP-compliant by default** — Data Security Top 10 and Supply Chain (A03:2025) baked in: no credential leakage, parameterized queries, pinned dependencies, CVE checks, PII masking.
- **Harness engineering** — agents run inside a structured harness of guardrails, role definitions, skill boundaries, and memory. Consistent, auditable behavior without custom prompt engineering per project.
- **Separation of duties** — implementation, testing, and security review are distinct agents. Nothing reaches production without a human sign-off.
- **Quality gates at every layer** — mandatory Great Expectations checks at bronze, silver, and gold. Failed DQ stops the pipeline; agents do not auto-retry.
- **Token savings** — RTK optimizer cuts shell-output tokens 60–90%, keeping long sessions economical.
