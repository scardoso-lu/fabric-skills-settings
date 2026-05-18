# Agent Map

Shows which **agents** are bound to which **rules** and **templates**, and which **rules** each **template** formalises.

> **Scope**: source-package relationships. Rules live under `rules/` in this package and are installed into target repos as `memory/rules/`, then loaded through `memory/MEMORY.md`. Templates remain source-only human-facing artefacts referenced by format, not by file-read at runtime.

```mermaid
flowchart LR
  subgraph AG["Agents — .claude/agents/"]
    a_dev["developer"]
    a_orch["orchestrator"]
    a_test["tester"]
    a_op["operator"]
  end

  subgraph R["Rules — rules/ source → memory/rules/ target"]
    r_de["data-engineering.md"]
    r_fp["fabric-platform.md"]
    r_sec["security.md"]
  end

  subgraph TP["Templates — templates/ ⚠ source-only"]
    tp_run["runbook.md"]
    tp_sec["security-review.md"]
    tp_dq["data-quality-checklist.md"]
    tp_ar["access-review.md"]
    tp_inc["incident-report.md"]
    tp_pb["pipeline-brief.md"]
    tp_rc["release-checklist.md"]
  end

  %% Agents → Rules  (inline rule codes in agent guidance)
  a_dev -- "SEC-08 injection\nSEC-10 pin deps\nSEC-12 SBOM" --> r_sec
  a_dev -- "DE-01 idempotency\nDE-02 lineage\nDE-09 testing\nDE-10 quality" --> r_de
  a_dev -- "FP-01 async APIs\nFP-03/04 notebook loop\nFP-07 ingestion\nFP-10 maintenance" --> r_fp
  a_test -- "DE-04 quality gates\nDE-02 lineage envelope" --> r_de
  a_test -- "DATA3 PII masking\nDATA7 data handling" --> r_sec
  a_test -- "FP-03/04 smoke + monitor\nFP-05 Spark vs SQL" --> r_fp
  a_op -- "DATA1–DATA10\nA03:2025 supply chain" --> r_sec
  a_op -- "FP-02 auth\nFP-06 lakehouse boundaries\nFP-10 maintenance review" --> r_fp
  a_orch -- "FP scope routing\nnotebook/pipeline handoff" --> r_fp

  %% Agents → Templates  (confirmed explicit reference)
  a_dev -- "via fabric-ops skill\n(runbook format)" --> tp_run

  %% Rules → Templates  (inferred: template checks implement rule requirements)
  r_sec -. "SEC-01 secrets\nDATA2 access\nDATA3 breaches" .-> tp_sec
  r_sec -. "DATA2 least-privilege\nSEC-01 secrets" .-> tp_ar
  r_sec -. "DATA3 breach response\nSEC-07 logging" .-> tp_inc
  r_de -. "DE-04 quality gates\nDE-02 lineage fields" .-> tp_dq
  r_de -. "DE-01/02/08 pipeline design" .-> tp_pb
  r_fp -. "FP-10 VACUUM + maintenance" .-> tp_run
  r_de -. "DE-04/08 validation steps" .-> tp_rc
  r_fp -. "FP-03/05 notebook checks" .-> tp_rc
  r_sec -. "SEC-10/12 dependency audit" .-> tp_rc
```

**Solid arrows** = explicit reference found in source files.  
**Dashed arrows** = inferred from content coverage (template checks implement the named rules; no direct cross-file link exists).

## Agent skill registry

| Agent | Skills available | Rules embedded inline |
|---|---|---|
| `developer` | fabric-ingest, fabric-transform, fabric-model, fabric-notebook-loop, fabric-ops, fabric-pipeline, git-commit, mock-data, semantic-model | SEC-08, SEC-10, SEC-12, DE-01, DE-02, DE-09, DE-10, FP-01, FP-03, FP-04, FP-07, FP-10 |
| `tester` | fabric-validate, fabric-ops, semantic-model | DE-04, DE-02, DATA3, DATA7, FP-03, FP-04, FP-05 |
| `operator` | *(none — review only, no writes)* | DATA1–DATA10, A03:2025, FP-02, FP-06, FP-10 |
| `orchestrator` | prd, grill-me | FP routing and handoff boundaries |

`fabric-transform` and `fabric-model` are developer-owned authoring skills. `fabric-validate` is the tester-owned validation skill. Their direct rule anchors are DE-06, FP-08, and DE-04 respectively.

## Template coverage by rule domain

| Template | Primary rule domain | Rule codes |
|---|---|---|
| `runbook.md` | fabric-platform.md | FP-10 VACUUM, FP-08 Gold optimisation, FP-04 debug |
| `security-review.md` | security.md | SEC-01, DATA2, DATA3, DATA7 |
| `data-quality-checklist.md` | data-engineering.md + security.md | DE-04, DE-02, DATA3, DATA7, DATA9 |
| `access-review.md` | security.md | DATA2, SEC-01, SEC-11 |
| `incident-report.md` | security.md | DATA3, SEC-07, DATA7 |
| `pipeline-brief.md` | data-engineering.md | DE-01, DE-02, DE-08 |
| `release-checklist.md` | data-engineering.md + fabric-platform.md + security.md | DE-04, DE-08, FP-03, SEC-10, SEC-12 |
