# Project Antigravity — Claude Code Instructions

Reference implementation for secure, autonomous Data Engineering pipelines using the Medallion Architecture (Bronze → Silver → Gold) on local Delta Lake.

## Architecture Overview

- **Bronze**: Raw, immutable, append-only ingestion with in-memory sanitization barrier
- **Silver**: Deduplicated, type-enforced, cleaned data via Delta MERGE
- **Gold**: Aggregated Star Schema facts and dimensions for business reporting

Agents handle implementation; these rules define the governance they must follow.

---

## Multi-Agent Team

Project Antigravity operates as a coordinated team of four specialized agents. The orchestrating Claude session selects agents based on their `description` field in `.claude/agents/`.

### Roles and Responsibilities

| Agent | Model | Tools | Primary Responsibility |
| :--- | :--- | :--- | :--- |
| **data-architect** | Sonnet | Read, Glob, Grep | Schema design, dimensional modeling, lineage mapping, layer contracts |
| **data-steward** | Sonnet | Read, Glob, Grep, Bash | Compliance (GDPR/CCPA), security audits (SEC-01..SEC-06), data dictionary, access governance |
| **data-engineer** | Sonnet | Read, Glob, Grep, Bash, Write, Edit | Pipeline implementation (Bronze/Silver/Gold), environment setup, testing |
| **data-analyst** | Haiku | Read, Glob, Grep, Bash | DQ validation, metric verification, anomaly detection, quarantine reporting |

### Coordination Workflow

```
data-architect → data-steward → data-engineer → data-analyst
```

1. **Architect designs**: Produces a typed schema specification, lineage mapping, and Kimball dimensional model. Enforces GL-01..GL-04, BZ-03/BZ-06, SL-01/SL-04 at design time.
2. **Steward reviews**: Validates for GDPR/CCPA compliance, classifies data sensitivity (GL-07 mart assignment, GL-08 RLS), acts as approval gate for Gold schema changes (GL-10). Implementation does not begin until Steward approves.
3. **Engineer implements**: Writes and runs the pipeline following the approved design. Applies SEC rules during Bronze ingestion, CP rules throughout, and OPS-01 DAG ordering (Bronze → Silver → Gold, blocking on failure). Notifies Analyst on completion.
4. **Analyst validates**: Runs DQ gates (SL-04, GL-02, GL-03) against pipeline outputs and produces a structured validation report. Escalates to Steward (compliance issues) or Architect (structural/model issues).

### Tool Isolation Rationale

- **Architect**: Read-only — design must not accidentally mutate data or code.
- **Steward**: Read + Bash for audit tooling (Semgrep, Delta table inspection); no Write/Edit — violations are handed to Engineer for remediation.
- **Engineer**: Full access — sole implementation agent.
- **Analyst**: Read + Bash for queries and test execution; no Write/Edit — validation must not alter the data being validated. Haiku model is cost-appropriate for repetitive query-heavy checks.

---

## Security Policy

### Three Unshakeable Pillars
1. **Zero-Trust Ingestion** — Assume all incoming data is toxic (PII/Secrets) until proven otherwise.
2. **Immutable Audit** — Never delete history without a trace (Delta Time Travel).
3. **Ephemeral Secrets** — Agents never "know" credentials; they are injected only at runtime.

### Rule SEC-01: Secret Injection (12-Factor)
No agent shall ever possess a config file containing credentials. Use `os.environ['SRC_{NAME}_PASS']` strictly.

| Secret Type | Allowed | Prohibited |
| :--- | :--- | :--- |
| DB Passwords | `os.environ['SRC_DB_PASS']` | Hardcoded strings, `.env` files in code |
| AWS/Cloud Keys | IAM Role / Instance Profile | Long-lived Access Keys in code |
| API Tokens | Secrets Manager Reference | Plain text in `config.yaml` |

### Rule SEC-02: The Sanitization Barrier (Bronze — "No-Write" Policy)
Strict order of operations in the Bronze Agent:
1. **Fetch** — Pull data from source to **RAM only**
2. **Sanitize** — Apply regex masking in RAM
3. **Write** — Only then write to Delta Lake

Writing raw unmasked data to any disk location (including `/tmp/debug.json`) is a **Severity 1 Security Incident**.

### Rule SEC-03: Toxic Data Classification

| Category | Pattern | Action | Result |
| :--- | :--- | :--- | :--- |
| Credit Card (PAN) | `\b(?:\d[ -]*?){13,16}\b` | Mask (last 4 visible) | `XXXX-XXXX-XXXX-1234` |
| Passwords | Keys matching `pass`, `pwd`, `secret` | Drop or Hash | `[REDACTED]` |
| API Bearer Tokens | `Bearer\s+[a-zA-Z0-9\-\._~\+\/]+=*` | Redact | `Bearer *****` |

### Rule SEC-04: Storage Encryption
- **At Rest**: All Delta Tables must use Server-Side Encryption (SSE-S3 or KMS).
- **In Transit**: Enforce `sslmode=require` (Postgres) or `useSSL=true` (MySQL).

### Rule SEC-05: Right to be Forgotten (GDPR/CCPA)
Deletions are processed in Silver via Delta's `DELETE` command. A `VACUUM` must run within 7 days to physically purge Parquet files.

### Rule SEC-06: Security Envelope Columns
Every record must carry:
- `_ag_ingest_timestamp` — When was this data admitted?
- `_ag_source_system` — Who provided this data?
- `_ag_batch_id` — Which job run is responsible?

### Incident Response
1. **Stop the Bleeding**: Revoke and rotate the compromised credential immediately.
2. **Clean the Lake**: Run `DELETE` then `VACUUM` (not just overwrite — Time Travel keeps old versions).
3. **Patch the Agent**: Update Bronze regex filters.
4. **Report**: Notify `#antigravity-security`.

### Developer Checklist (before merging to `antigravity-core`)
- [ ] `pre-commit` ran without errors (Semgrep scanner)
- [ ] No raw dicts logged (`print(payload)` is forbidden)
- [ ] New sources have their toxic field regex registered

---

## Bronze Layer Rules

**Objective**: Secure, Immutable, Traceable Ingestion into Delta Lake.

### Rule BZ-01: Sanitization at the Gate
Bronze is not a raw dump. No payload containing PCI, PII, or credentials shall be written to disk — even in Bronze.

### Rule BZ-02: Field-Level Masking

| Data Type | Action | Result |
| :--- | :--- | :--- |
| Credit Card (PAN) | Mask | `XXXX-XXXX-XXXX-1234` |
| Passwords | Drop/Hash | `[REDACTED]` or SHA-256 |
| API Keys/Tokens | Redact | `[REDACTED]` |

### Rule BZ-03: Metadata Injection
Inject into every record before writing:
- `_ag_ingest_timestamp`: UTC timestamp
- `_ag_source_system`: Origin identifier (e.g., `Shopify_Prod`)
- `_ag_batch_id`: Unique UUID for the execution job

### Rule BZ-04: Immutable Append-Only
- Always use `mode="append"`. Bronze is WORM (Write-Once, Read-Many).
- Never update; if source data changes, insert a new row with a new timestamp.
- Partition by `_ag_ingest_date=YYYY-MM-DD` for high-volume tables.

### Rule BZ-05: Dead Letter Queue (DLQ)
Agents must not crash on malformed data.
- Sanitization failure → drop row to DLQ.
- Schema type violation (uncastable) → move record to `bronze_quarantine` Delta Table.

### Rule BZ-06: Schema Evolution
Enable `mergeSchema=True`. New columns are allowed. Type changes (`int` → `string`) trigger a DLQ failure.

### Rule BZ-07: Idempotency
Use `replaceWhere` (Partition Overwrite) when re-running historical batches to avoid duplicating data.

### Rule BZ-12: 12-Factor Connection Strategy
Read connection details strictly from environment variables at runtime:
```
SRC_{SOURCE_NAME}_HOST
SRC_{SOURCE_NAME}_TYPE
SRC_{SOURCE_NAME}_USER
SRC_{SOURCE_NAME}_PASS
```

### Rule BZ-14: Delta Standard
Write Delta Tables only — never raw JSON/CSV files. Reasons:
- ACID transactions (no partial writes on crash)
- Automatic compression (Snappy/Zstd)
- Schema enforcement

---

## Silver Layer Rules

**Objective**: Type-Safe, De-duplicated, Enterprise-Ready Data.

### Rule SL-01: Strict Schema Enforcement
Silver is the "Casting Director":
- Explicitly cast Bronze strings to `Integer`, `Timestamp`, `Boolean`, `Decimal`.
- If a value cannot be cast (e.g., `price="free"`), convert to `null` and flag the row.
- New valid columns are propagated via `mergeSchema=True`.

### Rule SL-02: Upsert Strategy (Deduplication)
Use Delta MERGE — never simple append.
- **Match on PK**: `UPDATE` only if incoming `_ag_ingest_timestamp` is newer.
- **No match**: `INSERT` the new record.
- Result: exactly one active, up-to-date record per ID.

### Rule SL-03: Null Strategy
- String fields: convert `null` → `""` or `"Unknown"`.
- Numeric fields: keep as `null` (never zero-fill).
- If a Primary Key (e.g., `user_id`) is `null`, drop the row entirely.

### Rule SL-04: Data Quality Gates
Every record must satisfy:
1. Range checks: `age > 0`, `price >= 0`.
2. Reference checks: `country_code` must match ISO-3166.
3. Failures go to `silver_quarantine` Delta Table (not deleted).

### Rule SL-05: Right to be Forgotten
```sql
DELETE FROM silver_users WHERE user_id = '123';
```
Follow with `VACUUM` to physically remove old Parquet files.

### Rule SL-06: Z-Ordering (Daily)
```sql
OPTIMIZE table_name ZORDER BY (event_time, customer_id)
```

### Rule SL-07: Time Travel Retention
Set `delta.logRetentionDuration = "30 days"` on Silver tables.

### Rule SL-08: ACID Guarantee
Delta guarantees no partial writes on crash. Multiple agents can write concurrently via Optimistic Concurrency Control.

### Rule SL-09: Circuit Breaker
If Bronze schema has a radical, unrecoverable mismatch (e.g., `order_id` changed from `Int` to `String`), fail safely and alert the Data Engineering team.

---

## Gold Layer Rules

**Objective**: High-Performance, Governance-Ready, Boardroom-Quality Data.

### Rule GL-01: Dimensional Modeling (Kimball Star Schema)
- **Fact Tables** (`fact_orders`, `fact_page_views`): measurable events, immutable, contain FK + metrics.
- **Dimension Tables** (`dim_customers`, `dim_products`): descriptive attributes, slowly changing.

### Rule GL-02: Metric Standardization
Business logic (e.g., "What is Churn?") is calculated in the Gold Agent — never in the BI tool.

### Rule GL-03: Referential Integrity Gate
Before writing to a Fact table, verify that dimension keys exist in the dimension table. If a dimension is missing (Late Arriving Dimension), link to the `-1` / `Unknown` dimension key — never drop the fact row.

### Rule GL-04: Aggregation Granularity
Maintain one atomic fact table (lowest grain) and multiple aggregate tables:
- `fact_sales_atomic` — every single line item
- `fact_sales_monthly_kpi` — sum of revenue by Region by Month

### Rule GL-05: Z-Ordering (After Every Write)
```sql
OPTIMIZE fact_orders ZORDER BY (order_date, region_id)
```
Run immediately after every write job. Can speed up dashboard queries by 50x.

### Rule GL-06: Liquid Clustering (>1TB tables)
Use Liquid Clustering instead of Partitioning to prevent the Small File Problem for large cross-partition queries.

### Rule GL-07: Data Mart Isolation
Gold is divided into access-controlled Marts:
- **Finance Mart**: Finance Team + CFO only
- **Marketing Mart**: Marketing Analysts
- **Public Mart**: High-level KPIs for the whole company

### Rule GL-08: Row-Level Security
Multi-tenant tables enforce security at the view level: a user querying `gold_sales` sees only rows where `region_id` matches their assignment.

### Rule GL-09: Dependency Awareness
Gold jobs must **never** run until Silver jobs are confirmed successful.
DAG trigger: `Silver_Sales_Completed` → `Gold_Sales_KPI_Start`.

### Rule GL-10: Schema Locking (Contract)
Gold schemas are a contract. Schema evolution is **disabled** by default. Adding a column requires a PR and a backfill plan.

---

## Operations & Governance

### Rule OPS-01: DAG Mandate
Pipelines run in strict layer order: `Bronze → Silver → Gold`.
If Bronze fails, Silver must not start.

### Rule OPS-02: Idempotent Re-Runs
Running the pipeline twice on the same data must produce the exact same result.
- Bronze: append-only (deduplication happens downstream).
- Silver/Gold: use MERGE or partition OVERWRITE, never plain APPEND.

### Rule OPS-03: Vacuum Policy
Run `VACUUM` on all Delta Tables once a week. Retention: 7 days (168 hours).
```python
delta_table.vacuum(retention_hours=168)
```
Never run with `retention=0` unless actively purging toxic data or fixing corruption.

### Rule OPS-04: Log Rotation
Application logs must rotate daily and delete after 14 days. Use Python's `RotatingFileHandler`.

### Rule OPS-05: README per Gold Mart
Every Gold Data Mart directory must have a `README.md` with:
1. Business definition of each metric
2. Owner (team/person who requested it)
3. Refresh rate

### Rule OPS-06: Schema Versioning
When changing a Silver/Gold schema, bump the semantic version:
```python
delta.userMetadata = {"version": "1.2.0"}
```

### Rule OPS-07: Code vs. Data Split
- Code: committed to Git. Zero tolerance for uncommitted work at end of day.
- Data (`data/` folder): not committed. Sync to external drive or S3 weekly via `rclone` or `aws s3 sync`.

### Rule OPS-08: Clean Slate Protocol
A `setup.sh` must enable any new developer to bootstrap in <10 minutes:
1. Create virtual environment
2. Install `requirements.txt`
3. Create empty folder structures (`data/bronze`, `data/silver`, etc.)
4. Generate dummy `.env` from `.env.example`

### Rule OPS-09: Heartbeat Monitoring
- **Success**: Print `✓ Pipeline Finished: Processed X records` to stdout.
- **Failure**: Print `✗ Pipeline Failed: [Error Message]` to stderr.
- Track End-to-End Latency (Bronze start → Gold end). Rising latency signals a need for Z-Order optimization.

---

## Code Principles

### Rule CP-01: Environment Parity
Never use absolute paths. Use relative paths or environment variables.
```python
DATA_DIR = os.getenv('DATA_DIR', './data')
df = pd.read_csv(f"{DATA_DIR}/raw.csv")
```

### Rule CP-02: Containerization Ready
- No GUI dependencies (`matplotlib.pyplot.show()`, `input()` are forbidden).
- Stream all logs to stdout (Docker-compatible).

### Rule CP-03: No-Hardcode Zone
Treat local code as if it were public. Use `.env` files (in `.gitignore`) — never paste secrets inline.

### Rule CP-04: Safe-Fail Block
All IO operations (network/disk) must be wrapped in `try/except`. Silent failure is forbidden — log the specific error and re-raise or send to DLQ.

### Rule CP-05: Type Hinting (Strict)
All function signatures must be typed:
```python
def mask_pan(pan: str) -> str: ...
```

### Rule CP-06: Function Atomicity
One function, one job. If a function exceeds 50 lines, refactor it.

### Rule CP-07: Import Grouping
Standard library → Third-party → Local modules. `from module import *` is strictly prohibited.

### Rule CP-08: .gitignore Treaty
Mandatory entries:
```gitignore
.env
__pycache__/
*.csv
*.json
*.parquet
data/
logs/
.delta_log/
```

### Rule CP-09: Mock Data for Testing
Use the `Faker` library with `Faker.seed(42)` for deterministic synthetic PII — never real customer data.

### Rule CP-10: Unit vs. Integration Tests
- Unit tests: pure logic, no disk IO, runs fast.
- Integration tests: full pipeline with local Delta table, runs slower.

### Rule CP-11: Clean Slate Fixtures
Each test run creates a temporary Delta directory and deletes it afterwards.

---

## Project Structure

```
antigravity/
├── src/
│   ├── bronze/          # Bronze Agent Code
│   ├── silver/          # Silver Agent Code
│   ├── gold/            # Gold Agent Code
│   └── shared/          # Common utils (masking, logging, config)
├── tests/               # Pytest
├── config/              # YAML configs (non-sensitive only)
├── data/                # LOCAL ONLY — ignored by Git
│   ├── landing/
│   ├── bronze/
│   └── silver/
├── .env.example
├── .gitignore
├── CLAUDE.md
├── requirements.txt
└── main.py
```
