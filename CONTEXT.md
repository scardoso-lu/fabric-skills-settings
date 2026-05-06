# Shared Context — Fabric Codex

## Domain

Microsoft Fabric enterprise data platform. Workloads include:
- **Lakehouse** — Delta Lake storage, Spark compute (PySpark / SparkSQL / SparkR)
- **Warehouse** — T-SQL serverless analytics warehouse
- **Data Factory** — low-code pipeline orchestration (Copy, Dataflow Gen2)
- **Notebooks** — PySpark notebooks with # %% cell markers
- **Real-Time Intelligence** — Eventstream ingestion + Eventhouse (KQL) analytics
- **Power BI** — semantic models, reports, DAX/TMDL authoring
- **OneLake** — unified storage layer underlying all Fabric items

## Medallion Architecture (default pattern)

| Layer | Purpose | Storage | Write Mode |
|---|---|---|---|
| Bronze | Raw, immutable ingestion | Lakehouse Files/ or Tables/ | Append-only |
| Silver | Cleaned, typed, deduplicated | Lakehouse Tables/ (Delta) | MERGE / upsert |
| Gold | Aggregated, business-ready | Lakehouse Tables/ or Warehouse | MERGE or overwrite partition |

Agents use this pattern by default but are not limited to it. Other patterns (ODS, data vault, wide tables, streaming) are valid when appropriate.

## Shared Language

| Term | Meaning |
|---|---|
| **source contract** | Compact spec: source, schema, grain, keys, cadence, sensitive fields |
| **pipeline brief** | Business purpose + scope + expected output + constraints |
| **validation evidence** | Structured test report: row counts, DQ checks, anomalies |
| **runbook** | Schedule, dependencies, failure modes, recovery steps |
| **sandbox** | Local dev environment — never touches production Fabric workspace |
| **Key Vault ref** | `@Microsoft.KeyVault(SecretUri=...)` — how secrets are referenced in Fabric |

## Fabric CLI Essentials

```bash
fab auth login              # device-code auth; token cached at ~/.config/fab/cache.bin
fab import <path>           # deploy notebook or item to Fabric workspace
fab job run <item-id>       # trigger a notebook run
nbmon status <run-id>       # 7-line diagnostic banner (ONLY viable debug path)
```

## Operating Assumptions

- All agent work happens in sandbox/dev workspace unless explicitly stated otherwise.
- Credentials are never stored in code — always via environment variables or Key Vault refs.
- The user may be a newcomer on day one or an experienced Fabric engineer.
- Agents adapt their depth to what the user actually needs, not to a fixed workflow.
