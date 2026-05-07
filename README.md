# Fabric Agent Pack

Vendor-native Codex and Claude Code profiles for Microsoft Fabric data engineering.

This repository is an installer/source package. It should not be used as the day-to-day Fabric project workspace. Install one or both profiles into the actual project repository, then open Codex or Claude Code from that target repository root.

## Profiles

| Profile | Installs |
|---|---|
| Codex | `AGENTS.md`, `.agents/skills/*/SKILL.md`, `.codex/agents/*.toml`, `.codex/config.toml` |
| Claude | `CLAUDE.md`, `.claude/skills/*/SKILL.md`, `.claude/agents/*.md`, `.claude/settings.json` |
| Shared | `memory/`, placeholder `.env.example`, `.gitignore` block, `src/notebooks/`, `data/sandbox/`, `contracts/`, `runbooks/`, selected `bin/` tooling |

Profiles own their own instructions, skills, agents, and settings. The only shared runtime state is `memory/`.

## Install into a target repository

```bash
# from this source package
./bin/install-fabric-agent --profile codex  --target /path/to/project-repo --dry-run
./bin/install-fabric-agent --profile claude --target /path/to/project-repo --dry-run
./bin/install-fabric-agent --profile all    --target /path/to/project-repo --dry-run

# apply after reviewing the plan
./bin/install-fabric-agent --profile all --target /path/to/project-repo
```

Then work from the target repository:

```bash
cd /path/to/project-repo
codex   # or claude
```

## Safety behavior

`bin/install-fabric-agent` requires a git target, refuses to install into this source repo unless `--self-test` is passed, protects unmanaged files by default, supports `--backup`, and merges a managed `.gitignore` block idempotently.

## Validation

```bash
python3 bin/validate-install-package.py
python3 bin/validate-agent-guidance.py
```

For installer changes, also run a disposable-target smoke test:

```bash
tmp=$(mktemp -d)
git init -q "$tmp"
./bin/install-fabric-agent --profile all --target "$tmp" --dry-run
./bin/install-fabric-agent --profile all --target "$tmp"
./bin/install-fabric-agent --profile all --target "$tmp" --check
```

## Roadmap

Track implementation status and course corrections in `docs/vendor-native-installation-plan.md`.
