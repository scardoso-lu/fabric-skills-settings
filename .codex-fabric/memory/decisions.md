# Architecture Decisions

<!-- Agents: append an entry when you make a non-obvious design choice that future sessions need to know about. -->
<!-- Format: date, decision, why, alternatives considered -->
<!-- Example below — delete or replace after your first real decision. -->

---

## Template

```
<!-- YYYY-MM-DD -->
**Decision**: <what was decided>
**Why**: <reason — constraint, tradeoff, stakeholder requirement>
**Alternatives considered**: <what was rejected and why>
**Impact**: <what this affects going forward>
```

---

*(no decisions logged yet)*

<!-- Example dated decision:
**Decision**: Use local CSV mock data for ORDERS source until the upstream file drop is available.
**Why**: Keeps day-one development sandbox-only and avoids handling live credentials.
**Alternatives considered**: Direct API connection rejected until operator approval and Key Vault references exist.
**Impact**: Developer must generate mock data with Faker seed 42 under `data/sandbox/` and register `SRC_ORDERS_*` placeholders.
-->

<!-- 2026-05-06 -->
**Decision**: Treat external skill packs as optional reference material, not authoritative project workflow.
**Why**: The repository's purpose is a safe, newcomer-ready Fabric wrapper with bundled rules and core skills that must stay consistent.
**Alternatives considered**: Installing or recommending external packs as default workflow was rejected because external content can drift independently.
**Impact**: Agents should read `roadmap/external-skills.md` before installation and prefer this repo's `rules/` and `skills/core/` when guidance conflicts.
