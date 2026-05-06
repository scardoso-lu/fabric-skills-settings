# External Skills Discovery Guide

External skills are optional extensions installed under `skills/external/` with `bin/install-skills.sh`. Install them only when they help a sandbox Fabric task; the bundled `skills/core/` remain the default operating model.

## Recommended Packs

| Pack | Install command | When to install | Notes |
|---|---|---|---|
| Microsoft Fabric skills | `./bin/install-skills.sh add microsoft/skills-for-fabric` | You need broader Microsoft-authored Fabric examples or patterns beyond the bundled core skills. | Review the downloaded skill files before use; external content can evolve independently of this repo. |
| Patrick Gallucci Fabric skills | `./bin/install-skills.sh add PatrickGallucci/fabric-skills` | You want community Fabric workflow examples for comparison or inspiration. | Treat as reference material and keep sandbox/security rules from this repo authoritative. |

## Commands

```bash
./bin/install-skills.sh list
./bin/install-skills.sh add <owner/repo>
./bin/install-skills.sh update [pack-name]
./bin/install-skills.sh remove <pack-name>
```

## Evaluation Checklist

Before using an external skill in project work:

- [ ] Read the external `SKILL.md` before following it.
- [ ] Confirm it does not ask for real credentials in chat or code.
- [ ] Confirm it keeps work in sandbox/dev unless operator approval exists.
- [ ] Prefer this repo's `rules/` files when external guidance conflicts.
- [ ] Record any non-obvious adoption decision in `.codex-fabric/memory/decisions.md`.
