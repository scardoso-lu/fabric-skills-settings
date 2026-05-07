# Vendor-Native Installation Plan

## Goal

Transform this repository from a runtime wrapper into a supported installer for Microsoft Fabric agent profiles. After installation, Claude Code and Codex must run from the target repository root using each vendor's native project layout. The wrapper repository remains the source package and maintenance workspace only.

## Core Decision

Profiles own all vendor-specific runtime assets. Shared means memory only.

| Scope | Codex profile | Claude profile | Shared |
|---|---|---|---|
| Entrypoint guidance | `AGENTS.md` | `CLAUDE.md` | None |
| Skills | `.agents/skills/<name>/SKILL.md` | `.claude/skills/<name>/SKILL.md` | None |
| Agents/subagents | `.codex/agents/*.toml` | `.claude/agents/*.md` | None |
| Settings/plugins | `.codex/config.toml`, Codex plugin paths if packaged | `.claude/settings.json`, Claude plugin paths if packaged | None |
| Persistent project state | Reads/writes shared `memory/` | Reads/writes shared `memory/` | `memory/` only |

## Current Problem to Correct

The current wrapper model makes this repository the authoritative harness while sending implementation work into another repository via `TARGET_REPO_PATH`. This creates a split runtime context and causes agents to mix wrapper files with target project files.

Specific problems to remove from installed runtime guidance:

- Agents operating from the wrapper repository while writing to a separate target repository.
- Installed instructions that mention `TARGET_REPO_PATH` as the normal runtime root.
- Installed instructions that say target repository `AGENTS.md` or `CLAUDE.md` should be ignored.
- Flat shared skill files used directly by both vendors.
- Shared runtime agent definitions reused across vendors.

## Target Repository Runtime Layout

When both profiles are installed, the target repository should look like this:

```text
target-repo/
├── AGENTS.md
├── CLAUDE.md
├── .agents/
│   ├── skills/
│   │   ├── fabric-ingest/SKILL.md
│   │   ├── fabric-transform/SKILL.md
│   │   ├── fabric-model/SKILL.md
│   │   ├── fabric-validate/SKILL.md
│   │   ├── fabric-notebook-loop/SKILL.md
│   │   └── fabric-ops/SKILL.md
├── .codex/
│   ├── config.toml
│   └── agents/
│       ├── orchestrator.toml
│       ├── developer.toml
│       ├── tester.toml
│       └── operator.toml
├── .claude/
│   ├── settings.json
│   ├── skills/
│   │   ├── fabric-ingest/SKILL.md
│   │   ├── fabric-transform/SKILL.md
│   │   ├── fabric-model/SKILL.md
│   │   ├── fabric-validate/SKILL.md
│   │   ├── fabric-notebook-loop/SKILL.md
│   │   └── fabric-ops/SKILL.md
│   └── agents/
│       ├── orchestrator.md
│       ├── developer.md
│       ├── tester.md
│       └── operator.md
├── memory/
│   ├── MEMORY.md
│   ├── project.md
│   ├── platform.md
│   ├── decisions.md
│   ├── runbooks/
│   └── security/
├── .env.example
├── src/notebooks/
├── contracts/
├── data/sandbox/
├── fabric_notebooks/
└── runbooks/
```

## Source Repository Layout to Build Toward

This repository should be reorganized into profile packages plus shared memory scaffolding:

```text
fabric-skills-settings/
├── AGENTS.md                         # contributor guidance for this installer repo only
├── CLAUDE.md                         # contributor guidance for this installer repo only
├── README.md
├── bin/
│   ├── install-fabric-agent
│   ├── validate-agent-guidance.py
│   └── validate-install-package.py
├── profiles/
│   ├── codex/
│   │   ├── AGENTS.md
│   │   ├── skills/
│   │   │   ├── fabric-ingest/SKILL.md
│   │   │   ├── fabric-transform/SKILL.md
│   │   │   ├── fabric-model/SKILL.md
│   │   │   ├── fabric-validate/SKILL.md
│   │   │   ├── fabric-notebook-loop/SKILL.md
│   │   │   └── fabric-ops/SKILL.md
│   │   ├── config.toml
│   │   └── agents/
│   ├── claude/
│   │   ├── CLAUDE.md
│   │   ├── settings.json
│   │   ├── skills/
│   │   │   ├── fabric-ingest/SKILL.md
│   │   │   ├── fabric-transform/SKILL.md
│   │   │   ├── fabric-model/SKILL.md
│   │   │   ├── fabric-validate/SKILL.md
│   │   │   ├── fabric-notebook-loop/SKILL.md
│   │   │   └── fabric-ops/SKILL.md
│   │   └── agents/
│   │       ├── orchestrator.md
│   │       ├── developer.md
│   │       ├── tester.md
│   │       └── operator.md
│   └── shared/
│       ├── memory/
│       │   ├── MEMORY.md
│       │   ├── project.md
│       │   ├── platform.md
│       │   ├── decisions.md
│       │   ├── runbooks/.gitkeep
│       │   └── security/.gitkeep
│       ├── .env.example
│       ├── .gitignore.fragment
│       └── project-layout/
│           ├── bin/build_fabric_notebooks.py
│           ├── bin/fab-sandbox
│           ├── bin/nbmon-sandbox
│           ├── bin/smoke-test-sandbox.sh
│           ├── bin/post-smoke-update.py
│           ├── src/notebooks/.gitkeep
│           ├── contracts/.gitkeep
│           ├── data/sandbox/.gitkeep
│           └── runbooks/.gitkeep
├── docs/
├── templates/
└── rules/
```

## Installer Contract

The installer must support profile-specific installation:

```bash
./bin/install-fabric-agent --profile codex  --target /path/to/repo
./bin/install-fabric-agent --profile claude --target /path/to/repo
./bin/install-fabric-agent --profile all    --target /path/to/repo
```

Required options:

- `--dry-run`: show planned changes without writing.
- `--check`: verify an installed target repository without writing.
- `--force`: allow overwriting non-managed files after explicit user intent.
- `--backup`: copy replaced files to a timestamped backup path.

Default safety behavior:

- Refuse targets that are not git repositories.
- Refuse to install into this source repository unless `--self-test` is passed.
- Refuse to overwrite existing `AGENTS.md`, `CLAUDE.md`, `.claude/settings.json`, or profile assets unless managed markers are present or `--force` is passed.
- Merge `.gitignore` fragments instead of replacing `.gitignore`.
- Never copy `.env`.
- Never copy local wrapper memory by default.
- Never write real Fabric IDs, secrets, source credentials, tokens, or connection strings.

## Installation Mapping

| Source | Target |
|---|---|
| `profiles/codex/AGENTS.md` | `AGENTS.md` |
| `profiles/codex/config.toml` | `.codex/config.toml` |
| `profiles/codex/skills/*` | `.agents/skills/*` |
| `profiles/codex/agents/*.toml` | `.codex/agents/*.toml` |
| `profiles/claude/CLAUDE.md` | `CLAUDE.md` |
| `profiles/claude/settings.json` | `.claude/settings.json` |
| `profiles/claude/skills/*` | `.claude/skills/*` |
| `profiles/claude/agents/*` | `.claude/agents/*` |
| `profiles/shared/memory/*` | `memory/*` |
| `profiles/shared/.env.example` | `.env.example` |
| `profiles/shared/.gitignore.fragment` | merged into `.gitignore` |
| `profiles/shared/project-layout/*` | matching project paths, including neutral target `bin/` helpers |

## Work Phases

### Phase 0 — Verify Vendor Paths

Objective: avoid encoding assumptions that drift from Claude or Codex best practices.

Tasks:

- Verify Codex repository guidance, skills, plugin, memory, and agent/subagent paths from official documentation.
- Verify Claude Code project guidance, skills, subagents, settings, plugin, and memory paths from official documentation.
- Record confirmed paths in this plan before creating installer mappings.
- Codex project agents are installed as standalone TOML files under `.codex/agents/`; global agent settings install to `.codex/config.toml`.

Exit criteria:

- A confirmed path table is added to this plan.
- Any unverified vendor feature is marked deferred, not guessed.

### Phase 1 — Package Skeleton

Objective: create the profile package layout without changing runtime behavior yet.

Tasks:

- Add `profiles/codex/`, `profiles/claude/`, and `profiles/shared/`.
- Move or copy current guidance into draft profile files.
- Convert flat `skills/*.md` into profile-local `SKILL.md` directories.
- Add shared memory templates under `profiles/shared/memory/`.
- Add `.gitignore.fragment` and placeholder-only `.env.example` under `profiles/shared/`.

Exit criteria:

- Codex and Claude profile assets are isolated.
- Shared profile contains memory and neutral project scaffolding only.
- No runtime profile file tells agents to operate from the wrapper repository.

### Phase 2 — Installer

Objective: install profile packages into a target repository safely.

Tasks:

- Implement `bin/install-fabric-agent`.
- Support `--profile codex|claude|all`.
- Support `--target`, `--dry-run`, `--check`, `--force`, `--backup`, and `--self-test`.
- Add managed markers for files the installer owns.
- Merge `.gitignore` fragments idempotently.
- Create missing shared memory files without overwriting existing project state.

Exit criteria:

- Dry-run produces a complete file operation plan.
- Re-running install is idempotent.
- Existing non-managed target files are protected by default.

### Phase 3 — Validation

Objective: prevent profile drift and wrapper concepts from leaking into installed runtime files.

Tasks:

- Add `bin/validate-install-package.py`.
- Validate that all required profile files exist.
- Validate that Codex and Claude skills have matching names.
- Validate that Codex and Claude agents have matching role names where both are implemented.
- Validate that shared memory is the only shared runtime state.
- Validate that installed profile files do not contain forbidden phrases:
  - `TARGET_REPO_PATH`
  - `wrapper repo`
  - `configuration wrapper`
  - `ignore target repo instructions`
  - `this repo is the authoritative harness`
- Validate placeholder-only `.env.example` content.
- Keep `python3 bin/validate-agent-guidance.py` passing during the transition.

Exit criteria:

- Existing guidance validation passes.
- New install-package validation passes.
- A disposable target repo check passes for each profile and `all`.

### Phase 4 — Runtime Guidance Rewrite

Objective: make installed guidance target-repo-native.

Tasks:

- Rewrite installed `AGENTS.md` as concise Codex target-repo guidance.
- Rewrite installed `CLAUDE.md` as concise Claude target-repo guidance.
- Rewrite Claude agents as Claude-native subagents with vendor-specific frontmatter.
- Install Codex agents as `.codex/agents/*.toml` with concise role-specific `developer_instructions`.
- Keep detailed workflow steps in profile skills rather than giant root guidance files.

Exit criteria:

- Installed guidance says agents work in the target repository root.
- Installed guidance points to vendor-local skills and agents.
- Installed guidance uses shared `memory/` for project state only.

### Phase 5 — Wrapper Deprecation and Migration

Objective: turn this repository into a source package and migration tool.

Tasks:

- Rewrite root `AGENTS.md` and `CLAUDE.md` for installer-repo contribution only.
- Update `README.md` to explain install-first usage.
- Deprecate normal runtime use of `TARGET_REPO_PATH`.
- Add migration notes for existing users.
- Optionally add a migration command that reads wrapper `.env` only to discover an existing target path, then installs profiles into that target.

Exit criteria:

- New users are instructed to install into the target repo, then run Claude/Codex from the target repo root.
- Existing wrapper users have a migration path.
- The wrapper no longer presents itself as the active Fabric runtime workspace.

## Iteration Review Loop

Use this loop after every implementation phase:

1. Re-state the goal: vendor-native profiles, shared memory only, target repo as runtime root.
2. Compare the current diff against the goal.
3. Run validations.
4. Install into a disposable target repo with `--dry-run`, then real install.
5. Ask two smoke-test prompts from the target repo root:
   - "Where should notebooks be written?"
   - "Which repository are you operating in?"
6. Correct course immediately if the answer points back to the wrapper repository or to `TARGET_REPO_PATH` as the normal runtime root.
7. Update the phase status table in this plan.

## Phase Status

| Phase | Status | Last Reviewed | Notes |
|---|---|---|---|
| Phase 0 — Verify Vendor Paths | Completed | 2026-05-07 | Verified Codex `AGENTS.md`, `.agents/skills`, `.codex/agents/*.toml`, `.codex/config.toml`, and Claude `.claude/*` profile paths. |
| Phase 1 — Package Skeleton | Completed | 2026-05-07 | Added `profiles/codex`, `profiles/claude`, and `profiles/shared`; copied skills into vendor-native `SKILL.md` directories and moved target scaffolding/tooling into `profiles/shared/project-layout`. |
| Phase 2 — Installer | Partial | 2026-05-07 | Added `bin/install-fabric-agent` with profile selection, dry-run, check, force, backup, self-test, git target validation, and gitignore merge. |
| Phase 3 — Validation | Partial | 2026-05-07 | Added `bin/validate-install-package.py`; package and disposable target install checks pass. |
| Phase 4 — Runtime Guidance Rewrite | Partial | 2026-05-07 | Added target-native Codex and Claude profile guidance plus role agents; remaining work is deeper role/skill refinement and plugin packaging. |
| Phase 5 — Wrapper Deprecation and Migration | Partial | 2026-05-07 | Root `AGENTS.md`, `CLAUDE.md`, `README.md`, setup, and guidance map now describe source-package/installer usage; migration command and plugin packaging remain future work. |

## Implementation Progress

| Date | Status | Completed | Partial / Remaining |
|---|---|---|---|
| 2026-05-07 | Partial implementation | Added vendor-native profile package directories, shared memory templates, placeholder env/gitignore scaffolding, profile-aware installer, install-package validator, Codex `.codex/agents/*.toml`, Claude `.claude/agents/*.md`, profile-local skills, target-local helper scripts, and source-package root guidance. | Plugin packaging, migration command, and deeper profile refinements remain future work. |

## Course-Correction Log

| Date | Observation | Correction |
|---|---|---|
| 2026-05-06 | Initial installer concept introduced a custom `.fabric-agent/` runtime directory. | Rejected. Use vendor-native profile folders; shared memory is the only shared runtime layer. |
| 2026-05-06 | Earlier profile split kept agents outside the profile boundary. | Corrected. Agents belong to each vendor profile; only memory is shared. |
| 2026-05-07 | Implementing the plan surfaced the confirmed Codex project agent path as `.codex/agents/*.toml`, not `.agents/agents/`. | Updated this plan and the installer mapping to use `.codex/agents/*.toml` plus `.codex/config.toml`. |
| 2026-05-07 | Main-branch cleanup found leftover root runtime assets (`.claude/`, `skills/`, root `.env.example`, and external skill installer) plus target scripts that still assumed wrapper-based paths. | Removed root runtime assets, rewrote root guidance/setup for source-package usage, and installed neutral target helper scripts from `profiles/shared/project-layout/bin`. |

## Open Questions

- Should Codex role agents include explicit `skills.config` entries, or rely on repo skill discovery from `.agents/skills`?
- Should target repo `memory/*.md` be committed by default, or should only `memory/MEMORY.md` be committed with local state ignored?
- Should shared `runbooks/` live under `memory/runbooks/`, top-level `runbooks/`, or both with distinct purposes?
- Should profile installation be source-copy based, template-rendered, or both?
- Should Claude plugin packaging and Codex plugin packaging be separate later distribution artifacts after direct project install stabilizes?

## Definition of Done

- `bin/install-fabric-agent --profile codex --target <repo>` installs Codex-native assets and shared memory scaffolding.
- `bin/install-fabric-agent --profile claude --target <repo>` installs Claude-native assets and shared memory scaffolding.
- `bin/install-fabric-agent --profile all --target <repo>` installs both profiles without profile bleed-through.
- The target repo can be opened directly by Claude Code or Codex without referencing this wrapper repository.
- Installed runtime guidance does not mention `TARGET_REPO_PATH` as normal runtime behavior.
- Installed runtime guidance does not instruct agents to ignore target repo guidance.
- Shared runtime state is limited to `memory/`.
- Validation catches drift, forbidden wrapper concepts, missing skills, missing agents, and non-placeholder environment values.
