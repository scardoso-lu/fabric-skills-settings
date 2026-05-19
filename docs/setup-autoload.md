# Auto-Loaded Setup — Claude and Codex

What each runtime loads automatically when started in a target repository (after `fabric-skills-settings install`).

## Installation targets

| Source path | Claude target | Codex target |
|---|---|---|
| `profiles/claude/CLAUDE.md` | `CLAUDE.md` | — |
| `profiles/claude/settings.local.json` | `.claude/settings.local.json` | — |
| `profiles/skills/*/SKILL.md` | `.claude/skills/<skill>/SKILL.md` | `.agents/skills/<skill>/SKILL.md` |
| `profiles/claude/agents/*.md` | `.claude/agents/<name>.md` | — |
| `profiles/codex/AGENTS.md` | — | `AGENTS.md` |
| `profiles/codex/config.toml` | — | `.codex/config.toml` |
| `profiles/codex/agents/*.toml` | — | `.codex/agents/<name>.toml` |
| `profiles/shared/memory/*` | `memory/*` | `memory/*` |
| `profiles/shared/project-layout/**` | `tool/`, `.mcp.json`, `contracts/`, `data/`, `runbooks/`, `workspace/`, `memory/notebook-authoring.md`, `memory/pipeline-authoring.md`, `memory/rules/` | same |
| `profiles/shared/.env.example` | `.env.example` | `.env.example` |

The table shows all possible targets. `--profile claude` installs only the Claude column plus shared files, `--profile codex` installs only the Codex column plus shared files, and `--profile all` installs both columns plus shared files.

## Auto-load sequence — Claude Code

```mermaid
flowchart TD
  A["Claude Code starts in target repo"] --> B["Auto-loads CLAUDE.md"]
B --> C["Auto-loads .claude/settings.local.json\n(permissions, hooks, MCP servers)"]
  C --> D["Reads .mcp.json → registers MCP tools"]
  B --> E["CLAUDE.md Session Start procedure\n(agent executes these steps)"]
  E --> F["Reads memory/MEMORY.md"]
  F --> G["Reads memory/notebook-authoring.md\n(mandatory notebook rules)"]
  F --> H["Reads memory/rules/*.md\n(DE/FP/SEC rules)"]
  F --> R["Reads memory/RTK.md\n(token-proxy mandate)"]
  E --> I["Reads memory/skill-fixes/*.md\n(override SKILL.md defaults)"]
  E --> J["If topic-specific work:\nReads memory/<topic>/project.md"]
  E --> K["Runs setup verification checks\n(.env, fab, fab auth)"]

  B --> L["Sub-agents available via /agent\n.claude/agents/developer.md\n.claude/agents/orchestrator.md\n.claude/agents/tester.md\n.claude/agents/operator.md"]
  B --> M["Skills available via /skillname\n.claude/skills/*/SKILL.md\n(13 skills copied from profiles/skills)"]
```

## Auto-load sequence — Codex

```mermaid
flowchart TD
  A["Codex starts in target repo"] --> B["Auto-loads AGENTS.md"]
  B --> C["Auto-loads .codex/config.toml\n(reasoning effort, shell policy, MCP)"]
  C --> D["Reads .mcp.json → registers MCP tools"]
  B --> E["AGENTS.md Session Start procedure"]
  E --> F["Reads memory/MEMORY.md"]
  F --> G["Reads memory/notebook-authoring.md"]
  F --> H["Reads memory/rules/*.md"]
  F --> R["Reads memory/RTK.md"]
  E --> I["Reads memory/skill-fixes/*.md"]
  E --> J["If topic-specific work:\nReads memory/<topic>/project.md"]
  E --> K["Runs mandatory setup gate\n(.env, fab, fab auth)"]

  B --> O["Agents available\n.codex/agents/developer.toml\n.codex/agents/orchestrator.toml\n.codex/agents/tester.toml\n.codex/agents/operator.toml"]
  B --> L["Skills available\n.agents/skills/*/SKILL.md\n(13 skills copied from profiles/skills)"]
```

## Side-by-side comparison

| Concern | Claude Code | Codex |
|---|---|---|
| Primary guidance file | `CLAUDE.md` (root) | `AGENTS.md` (root) |
| Runtime config | `.claude/settings.local.json` | `.codex/config.toml` |
| Agent definitions | `.claude/agents/*.md` | `.codex/agents/*.toml` |
| Skills path | `.claude/skills/<skill>/SKILL.md` | `.agents/skills/<skill>/SKILL.md` |
| MCP config | `.mcp.json` | `.mcp.json` |
| Shared memory | `memory/MEMORY.md` + `memory/notebook-authoring.md` + `memory/rules/*.md` + `memory/RTK.md` | same |
| Session-start setup check | Yes — verifies `.env`, `fab`, `fab auth` | Yes — same check |
| Skill content | 13 skills from `profiles/skills/` (fabric-ingest, fabric-transform, fabric-model, fabric-validate, fabric-notebook-loop, fabric-ops, fabric-pipeline, mock-data, semantic-model, prd, grill-me, git-commit, caveman) | same 13 skills, copied from the same source |

## Files that are read only on demand (not auto-loaded)

| File | When read |
|---|---|
| `memory/<topic>/project.md` | When working on a specific topic |
| `memory/skill-fixes/<skill>-<slug>.md` | Session start (if any exist) |
| `memory/rules/*.md` | Session start through `memory/MEMORY.md` global files |
| `.claude/skills/<skill>/SKILL.md` or `.agents/skills/<skill>/SKILL.md` | When the skill is invoked |
| `.claude/agents/<name>.md` | When that sub-agent is spawned |
| `tool/**/*.py` | When an agent runs that tool via Bash |
