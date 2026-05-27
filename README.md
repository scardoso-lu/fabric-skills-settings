# Fabric Agent Pack

Vendor-native **Codex** and **Claude Code** profiles for Microsoft Fabric data engineering.

Fabric Agent Pack turns a normal git repository into a guided Microsoft Fabric project workspace. It installs agent instructions and lightweight scaffold files, while `fabric-vibe` provides the setup, validation, notebook, pipeline, lakehouse, and workspace helpers from the package.

> This repository is the **source package and installer**, not the day-to-day Fabric project workspace. Install a profile into your actual project repository, then run Codex or Claude Code from that target repository root.

**Overview**

![Fabric Agent Pack](img/overview.png)

## Quick start

The CLI is published as `fabric-vibecoding-settings` on PyPI. Installing it puts two console scripts on your PATH:

| Command | Role |
|---|---|
| `fabric-vibecoding-agents` | Install / check / refresh agent profiles in a project repo |
| `fabric-vibe` | Daily Fabric helpers run from a project repo (notebook, pipeline, lakehouse, workspace, lint, precommit) |

### Step 1 — Install the CLI

```bash
uv tool install fabric-vibecoding-settings        # recommended
# or
pip install fabric-vibecoding-settings
```


### Step 2 — Install a profile into your project repo

```bash
# preview
fabric-vibecoding-agents install --profile claude --target /path/to/project-repo --dry-run

# apply (also runs fabric-vibe setup: ms-fabric-cli + creds + workspaces.json)
fabric-vibecoding-agents install --profile claude --target /path/to/project-repo

# verify drift later
fabric-vibecoding-agents check --profile claude --target /path/to/project-repo
```

`fabric-vibecoding-agents install` copies the profile and scaffold files into the target, then runs `fabric-vibe setup` from the target root to install `ms-fabric-cli`, prompt for `FABRIC_TENANT_ID` / `CLIENT_ID` / `CLIENT_SECRET`, verify auth, and populate `workspaces.json`. Pass `--no-bootstrap` to skip.

### Step 3 — Daily work inside the project

Once a profile is installed, run the daily helpers via `fabric-vibe` from the project root:

```bash
fabric-vibe notebook build  <name>
fabric-vibe notebook deploy <name> <workspace_id>
fabric-vibe pipeline manage list
fabric-vibe lakehouse list-tables
fabric-vibe workspace switch <displayName>
fabric-vibe lint
fabric-vibe precommit
```

Each subcommand passes its trailing argv through to package-bundled helpers while preserving the target repo as the working directory. Use `fabric-vibe <group> --help` to see what each helper accepts.

### `fabric-vibecoding-agents` flags

| Flag | Effect |
|---|---|
| `--profile {codex,claude,all}` / `-p` | Pick the agent profile (required) |
| `--target <path>` / `-t` | Target git repository (required) |
| `--dry-run` | Preview changes without writing (install/refresh only) |
| `--force` | Overwrite non-managed existing files |
| `--backup` | Back up replaced files alongside the originals |
| `--no-bootstrap` | Copy files only; skip the post-install Fabric auth + workspaces.json bootstrap (install only) |
| `--verbose` / `-v` | Debug-level logging |
| `--quiet` / `-q` | Suppress info logging |
| `--help` / `-h` | Show usage |

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

Re-running the same install command is idempotent — credentials already set are skipped, and managed files only change when their source content changes. If you need to bootstrap again later (e.g. after rotating the secret), run `fabric-vibe setup` from inside the target.

## Docker image

The Fabric MCP server is also published as a Docker image on Docker Hub:

```bash
docker pull silviocardoso/fabric-vibecoding-mcp-server:latest
```

Image page: [silviocardoso/fabric-vibecoding-mcp-server](https://hub.docker.com/r/silviocardoso/fabric-vibecoding-mcp-server)

The image builds from `server/Dockerfile` and includes the server-side MCP tools plus the baked knowledge-graph artifacts. Use it when you want to run the MCP server from a published image instead of building it locally with `docker compose up --build`.

Minimal `docker-compose.yml` using the published image:

```yaml
services:
  server:
    image: silviocardoso/fabric-vibecoding-mcp-server:latest
    container_name: fabric-mcp-server
    environment:
      PORT: "8000"
      HOST: "0.0.0.0"
      LOG_LEVEL: ${LOG_LEVEL:-info}
    ports:
      - "127.0.0.1:8000:8000"
    restart: unless-stopped
```

Then start it with:

```bash
docker compose up
```

This binds the server to `127.0.0.1:8000`, so it is reachable from your machine without exposing it to the LAN.


## Learn more

- [docs/architecture.md](docs/architecture.md) — components, install flow, agents, MCP tools, Bash helpers, and folder layout.
- [docs/mcp-auth-flow.md](docs/mcp-auth-flow.md) — how `.mcp.json` is written, the host-only auth model, CORS, and audit logging.
- [docs/networkx-flow.md](docs/networkx-flow.md) — knowledge-graph build, BM25 + 1-hop re-rank, and the atomic write path.


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
