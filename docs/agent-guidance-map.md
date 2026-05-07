# Agent Guidance Map

This repository is the source package for vendor-native Fabric agent profiles. Runtime guidance is installed into target repositories; root guidance in this repository is for maintaining the installer package.

## Canonical sources

| Scope | Canonical file(s) | Notes |
|---|---|---|
| Source package contributor guidance | `AGENTS.md`, `CLAUDE.md` | Applies when editing this installer repository. |
| Codex installed runtime | `profiles/codex/AGENTS.md`, `profiles/codex/skills/*/SKILL.md`, `profiles/codex/agents/*.toml`, `profiles/codex/config.toml` | Installed into target repos by `bin/install-fabric-agent`. |
| Claude installed runtime | `profiles/claude/CLAUDE.md`, `profiles/claude/skills/*/SKILL.md`, `profiles/claude/agents/*.md`, `profiles/claude/settings.json` | Installed into target repos by `bin/install-fabric-agent`. |
| Shared target state | `profiles/shared/memory/` | Runtime sharing is memory only. |
| Shared target scaffolding/tooling | `profiles/shared/project-layout/`, `profiles/shared/.env.example`, `profiles/shared/.gitignore.fragment` | Neutral files installed to target repos. |
| Installer roadmap | `docs/vendor-native-installation-plan.md` | Phase status, review loop, course corrections, open questions. |
| Safety source material | `rules/`, `templates/` | Source package material used to maintain profile guidance. |

## Drift checks

Run this before PR handoff when instructions, profiles, installer logic, validation, or docs change:

```bash
python3 bin/validate-install-package.py
python3 bin/validate-agent-guidance.py
```

For installer mapping changes, also smoke-test against a disposable git repo with `--dry-run`, real install, and `--check`.

## Update protocol

1. Update the relevant profile owner first: `profiles/codex`, `profiles/claude`, or `profiles/shared`.
2. Keep profile-specific agents/skills/settings inside their profile; do not create root runtime folders.
3. Update `docs/vendor-native-installation-plan.md` phase status and course-correction notes.
4. Run validation and disposable-target install checks before committing.
