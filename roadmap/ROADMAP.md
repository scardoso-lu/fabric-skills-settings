# Fabric Codex — Improvement Roadmap

> Generated from a full project audit. Items are grouped by theme and ordered by impact.
> Bugs that would break day-one usage are marked **[DAY-ONE BUG]** and should be fixed before anything else.

---

## Already Fixed

- **[DAY-ONE BUG] `build_fabric_notebooks.py` wrong source directory** — script looked in `notebooks/` but setup.sh creates `src/notebooks/`. Fixed in `bin/build_fabric_notebooks.py`.

---

## P0 — Day-One Blockers

These prevent a newcomer from getting anything done.

### 1. Memory files have no seed examples

**Problem**: Every memory file opens with `*(none yet)*`. The orchestrator's first action is to check `memory/platform.md` for registered source systems — but the file is empty, so the conditional logic collapses. A newcomer has no model of what a filled entry looks like.

**Fix**:
- Add a commented-out example block to each memory file showing what a realistic entry looks like
- Add a note at the top of each file: `<!-- Example below — delete after your first real entry -->`
- Files to update: `memory/project.md`, `memory/platform.md`, `memory/decisions.md`

---

### 2. setup.sh doesn't guide Fabric infrastructure setup

**Problem**: setup.sh creates local folders and checks tools, then prints "Setup complete — fill in your .env values." A newcomer has no Fabric workspace, no lakehouses, and no idea what `BRONZE_LAKEHOUSE_ID` means or where to find it in the UI.

**Fix**:
- Add a post-setup checklist to setup.sh output:
  ```
  Next steps:
  1. Create a Fabric workspace: app.fabric.microsoft.com → Workspaces → New
  2. Copy the workspace ID from Settings → Workspace settings → paste into .env
  3. Create three lakehouses: bronze_lh, silver_lh, gold_lh
  4. Copy each Lakehouse ID from its Settings page → paste into .env
  5. Run: fab auth login
  ```
- Link to the Microsoft Fabric quickstart documentation

---

### 3. `fab auth login` is not verified

**Problem**: setup.sh checks that `fab` is installed but never verifies that authentication succeeded. A corporate proxy or expired token produces a silent failure that only surfaces later with a cryptic 401 on `fab import`.

**Fix**: Add an optional auth check to setup.sh:
```bash
if command -v fab &>/dev/null; then
    if fab api get /v1/me &>/dev/null 2>&1; then
        log_ok "Fabric auth: authenticated"
    else
        log_warn "Fabric auth: not authenticated — run 'fab auth login'"
    fi
fi
```

---

### 4. Source system registration workflow has no template

**Problem**: The orchestrator asks the user to declare a source system, then tells the developer to register it in `memory/platform.md` and add a `SRC_<SYSTEM>_*` block to `.env`. But:
- No example of what a platform.md entry looks like when populated
- No template for what the developer should write
- Unclear which agent is responsible for writing the `.env` block (developer writes it as a placeholder; human fills in values)

**Fix**:
- Add a filled example to `memory/platform.md`
- Add an explicit note in `developer.md`: "Write the `SRC_<SYSTEM>_TYPE` and `SRC_<SYSTEM>_PATH` placeholder block into `.env` — do not fill in any values, output placeholders only"

---

## P1 — Workflow Gaps

These make the agent workflow incomplete or ambiguous.

### 5. `fabric-notebook-loop` skill is missing the run ID capture step

**Problem**: The loop ends at `nbmon status $RUN_ID` but never shows how to capture `$RUN_ID` from `fab job run`. Without this, the developer cannot reach the monitoring step.

**Fix**: Update `skills/core/fabric-notebook-loop/SKILL.md` with:
```bash
# Run and capture the run ID
RUN_OUTPUT=$(fab job run --item-id $NOTEBOOK_ITEM_ID --workspace-id $WORKSPACE_ID)
RUN_ID=$(echo "$RUN_OUTPUT" | grep -oP 'runId["\s:]+\K[a-f0-9-]+')
echo "Run ID: $RUN_ID"

# Monitor
nbmon status $RUN_ID
```

---

### 6. Tester has no handoff step

**Problem**: Tester produces a structured report but there is no documented destination. Does it go to the orchestrator? Into memory? Into a file? The handoff section is missing from `tester.md`.

**Fix**: Add a handoff block to `tester.md`:
```
## Handoff
- Log result in `.codex-fabric/memory/project.md` (pipeline status table)
- If PASS → notify orchestrator: "Validation passed for <pipeline>, batch <id>"
- If FAIL / ESCALATE → notify orchestrator with escalation target and reason
- If runbook exists → append validation result to `memory/runbooks/<pipeline>.md`
```

---

### 7. Operator correction loop is undefined

**Problem**: Operator finds an issue and hands it back to the developer. But:
- Does the operator log the finding before or after remediation?
- After the developer fixes it, does the operator re-review or auto-approve?
- There is no "re-review" trigger documented.

**Fix**: Add to `operator.md`:
```
## Correction Loop
1. Log the finding immediately in memory/security/<scope>.md (pre-remediation)
2. Hand back to developer with a specific remediation list
3. When developer confirms fix, run the security checklist again on changed files only
4. Update the memory log with verdict: APPROVED and date
```

---

### 8. Quarantine escalation has no playbook

**Problem**: Tester escalates to operator when quarantine rate >5% for "possible data leak." But the operator has no documented response for this scenario — the security checklist is about code review, not data investigation.

**Fix**: Add a quarantine investigation section to `operator.md` or `templates/incident-report.md`:
- Query the quarantine table to read `_quarantine_reason` values
- Classify: schema mismatch vs. PII detection failure vs. validation rule failure
- If PII-related: trigger SEC-05 (deletion flow)
- If schema mismatch: hand back to architect (or developer)

---

### 9. Runbook template should be filled after first run, not before

**Problem**: Developer is told to create a runbook before running the pipeline. But fields like "Expected runtime" and "Expected row count" can only be known after the first successful run.

**Fix**: Split the runbook template into two phases:
```yaml
# Phase 1: fill before first run (what you know)
asset, schedule, dependencies, source, target, rollback command

# Phase 2: fill after first successful run (what you observed)
expected_runtime, expected_row_count, normal behavior, failure modes
```
Add a comment: `# Phase 2 fields — fill in after the first successful run`

---

## P2 — Content Gaps

These reduce quality but don't block the workflow.

### 10. Mock data generation has no reusable example

**Problem**: The orchestrator routes to the developer to generate mock data with Faker, but there's no standalone template or example. The developer has to infer the schema from the source contract and write Faker from scratch.

**Fix**: Add a `templates/mock-data-generator.py` scaffold:
```python
from faker import Faker
import pandas as pd

fake = Faker(); Faker.seed(42)

# Replace with actual schema from source-contract.yaml
rows = [{
    "id": i,
    "name": fake.name(),           # PII — will be masked in Bronze
    "email": fake.email(),          # PII — will be masked in Bronze
    "amount": float(fake.pydecimal(2, 2, positive=True)),
    "created_at": fake.date_this_year().isoformat(),
} for i in range(1, 1001)]

pd.DataFrame(rows).to_csv("data/sandbox/<system>.csv", index=False)
print(f"Generated {len(rows)} rows")
```

---

### 11. `fabric-ops` skill lacks concrete commands

**Problem**: The maintenance routine says "Daily: check pipeline run status" but gives no command. Does the developer use `fab`? A SQL query? The skill is high-level but not actionable.

**Fix**: Add a "Daily checks" command block:
```bash
# Check recent notebook runs (last 24h)
fab job list --workspace-id $WORKSPACE_ID --type Notebook

# Query quarantine tables for new rows
# (run in Fabric SQL endpoint)
SELECT _batch_id, _quarantine_reason, COUNT(*) as cnt
FROM bronze_quarantine
WHERE _ingest_date = CURRENT_DATE
GROUP BY 1, 2
ORDER BY cnt DESC;
```

---

### 12. `fabric-notebook-loop` skill needs a complete worked example

**Problem**: The skill shows individual steps but not an end-to-end example — from creating a local `.py` file to seeing a successful nbmon result.

**Fix**: Add a "Full Example" section showing a minimal notebook (two cells: load CSV → write to Bronze) going through the entire loop in one read.

---

### 13. External skills have no discovery guide

**Problem**: `bin/install-skills.sh add microsoft/skills-for-fabric` works, but there's no document explaining what's in that pack, why someone would install it, or what packs exist.

**Fix**: Add `roadmap/external-skills.md` listing recommended packs with a one-line description of each and when to install them.

---

## P3 — Consistency and Polish

### 14. Skill invocation syntax is aspirational

**Problem**: `developer.md` says "Invoke `/fabric-ingest` for source → Bronze ingestion" but `/fabric-ingest` is not a real Claude Code command. The actual mechanism is reading `skills/core/fabric-ingest/SKILL.md`.

**Options**:
- A: Update wording to "Read `skills/core/fabric-ingest/SKILL.md` before starting ingestion work"
- B: Configure actual slash commands in `.claude/settings.json` that load the skill file content

**Recommendation**: Option A now, Option B as a future enhancement.

---

### 15. CLAUDE.md and AGENTS.md agent descriptions slightly diverge

**Problem**: Minor wording differences in how agents are described between the two files. Low risk but reduces confidence that they're in sync.

**Fix**: Consider a single source of truth (for example, document canonical ownership in a guidance map) or add a local drift check that compares key references across runtime docs.

---

### 16. README lacks a Day One checklist

**Problem**: README has a Quick Start section but it's too abstract for someone who has never used Fabric.

**Fix**: Add a numbered checklist:
```markdown
## Day One Checklist
1. [ ] Clone this repo and run `./setup.sh --install-tools`
2. [ ] Create a Fabric workspace in app.fabric.microsoft.com
3. [ ] Create three lakehouses: bronze_lh, silver_lh, gold_lh
4. [ ] Copy their IDs into `.env`
5. [ ] Run `fab auth login`
6. [ ] Tell the orchestrator: "I need to build a test pipeline with mock orders data"
```

---


## Sprint Implementation — 2026-05-06

The roadmap was reviewed against the project purpose: a newcomer-ready, sandbox-first Microsoft Fabric data engineering wrapper. Items that strengthened day-one setup, safe source registration, validation handoff, security escalation, and reusable templates were implemented. Items that were aspirational or could conflict with the wrapper model were adjusted rather than copied verbatim.

| Item | Verdict | Implementation |
|---|---|---|
| 1. Memory seed examples | Accepted | Added commented examples to `project.md`, `platform.md`, and `decisions.md`. |
| 2. Fabric infrastructure setup guidance | Accepted | Added concrete workspace/lakehouse next steps and Microsoft Learn quickstart link to `setup.sh`; mirrored in `README.md`, `AGENTS.md`, and `CLAUDE.md`. |
| 3. Fabric auth verification | Accepted with safety adjustment | Added a bounded `fab api get /v1/me` auth check to `setup.sh` using `timeout` when available, so setup warns instead of failing. |
| 4. Source registration template | Accepted | Added source examples/template to `platform.md` and explicit developer guidance for placeholder-only `SRC_<SYSTEM>_*` entries. |
| 5. Run ID capture | Accepted with robust parsing | Updated `fabric-notebook-loop` with `RUN_OUTPUT` capture and Python-based JSON/text run ID parsing. |
| 6. Tester handoff | Accepted | Added tester handoff instructions in both Claude sub-agent and Codex guidance. |
| 7. Operator correction loop | Accepted | Added pre-remediation logging, developer handback, re-review, and final verdict workflow. |
| 8. Quarantine escalation playbook | Accepted | Added operator quarantine investigation and incident-report playbook. |
| 9. Runbook two-phase template | Accepted | Split `templates/runbook.md` into Phase 1 pre-run and Phase 2 post-success sections. |
| 10. Mock data generator | Accepted | Added `templates/mock-data-generator.py` using Faker seed 42 and `data/sandbox/` output. |
| 11. Fabric ops concrete commands | Accepted | Added daily `fab job list`, `nbmon`, and quarantine SQL examples. |
| 12. Notebook-loop full example | Accepted | Added CSV → Bronze worked example. |
| 13. External skills guide | Adjusted | Added `roadmap/external-skills.md`; external packs are optional references and repo rules remain authoritative. |
| 14. Skill invocation wording | Accepted | Replaced aspirational slash-command wording with direct `SKILL.md` reads. |
| 15. CLAUDE/AGENTS drift | Accepted pragmatically | Updated both files now; local drift check implemented in the remaining in-scope sprint work. |
| 16. README day-one checklist | Accepted | Added a newcomer checklist and corrected project structure details. |

---
## Future Ideas (not yet scoped)

All previously listed in-scope follow-up ideas were either implemented or adjusted in the remaining sprint implementation below. Out-of-scope automated external-service checks, negative-case expansion, and production handoff ideas are intentionally not listed.

---

## Summary

| Priority | Items | Status |
|---|---|---|
| Already fixed | 1 (`build_fabric_notebooks.py` path bug) | ✅ Done |
| P0 Day-One Blockers | 4 items | ✅ Done in 2026-05-06 sprint |
| P1 Workflow Gaps | 5 items | ✅ Done in 2026-05-06 sprint |
| P2 Content Gaps | 4 items | ✅ Done in 2026-05-06 sprint |
| P3 Polish | 3 items | ✅ Done in 2026-05-06 sprint |
| Remaining in-scope sprints | 4 implemented | ✅ Done |

---

## Remaining In-Scope Sprint Implementation — 2026-05-06

The remaining improvements were reviewed against the wrapper purpose and implemented only where they preserve local/sandbox operation and human control of environment-specific Fabric IDs. Sprint ideas for automated external-service checks, negative-case mock expansion, and production handoff automation were excluded as out of scope.

| Sprint | Theme | Fit review | Implementation |
|---|---|---|---|
| Sprint 8 | Source contract validator | Accepted — validates source readiness before agents build pipelines. | Added `bin/validate-source-contract.py` and `docs/examples/mock-orders-source-contract.yaml`. |
| Sprint 9 | Fabric sandbox smoke runbook | Accepted as human-run sandbox documentation only. | Added `docs/fabric-sandbox-smoke-test.md`. |
| Sprint 10 | MCP/read-only discovery hardening | Accepted with no token handling and no auto-write behavior. | Added `docs/fabric-mcp-readonly-discovery.md` and `bin/fabric-inventory-readonly`. |
| Sprint 11 | Agent guidance source map | Accepted as lightweight drift control, not generation complexity. | Added `docs/agent-guidance-map.md` and `bin/validate-agent-guidance.py`. |

## Remaining Backlog

| Idea | Status |
|---|---|
| Auto-populate `.env` from Fabric discovery | Closed as adjusted — use read-only discovery plus human copy/paste instead of automatic writes. |
| Semantic versioning for memory files | Closed as adjusted — use the guidance map and drift check; defer heavier versioning until real pipeline history exists. |
