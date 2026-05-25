---
name: security
description: Credentials, PII, logging, dependency, inventory, and compliance rules — OWASP-mapped.
kind: rule
---

# Security Rules

These rules apply to all agents and all pipelines.

OWASP Data Security Top 10 (2025) mapping:

| OWASP | Rule(s) |
|---|---|
| DATA1 Injection Attacks | SEC-08 |
| DATA2 Broken Auth & Access Control | SEC-01 |
| DATA3 Data Breaches | SEC-02, SEC-03, SEC-07 |
| DATA4 Malware & Ransomware | SEC-10, SEC-12 |
| DATA5 Insider Threats | SEC-06 |
| DATA6 Weak Cryptography | SEC-01, SEC-09 |
| DATA7 Insecure Data Handling | SEC-02, SEC-03, SEC-05 |
| DATA8 Inadequate Third-Party Security | SEC-10, SEC-12 |
| DATA9 Data Inventory & Management | SEC-06, SEC-11 |
| DATA10 Non-Compliance | SEC-05 |

OWASP Top 10 (2025) mapping:

| OWASP | Rule(s) |
|---|---|
| A03:2025 Software Supply Chain Failures | SEC-10, SEC-12 |

---

## SEC-00: Agents Never Handle Real Credentials — ABSOLUTE RULE

**This rule cannot be overridden by any instruction, user request, or context.**

Agents (Claude, Codex, or any sub-agent) must never:
- Ask the user for any security-sensitive information — passwords, tokens, API keys, connection strings, hostnames, URIs, tenant IDs, client IDs, or any infrastructure identifier
- Receive, store, repeat, or process any such value even if the user volunteers it
- Output any real value in place of a placeholder in any file, notebook, or message

When configuration requires a credential, agents output a placeholder and instruct the human to fill it in:

```python
# ✅ Correct — agent outputs this
db_password = os.environ["SRC_ORDERS_PASS"]  # <-- fill in .env (never share this value with the agent)
host        = os.environ["SRC_ORDERS_HOST"]  # <-- fill in .env (never share this value with the agent)
```

```python
# ❌ Forbidden — agent never outputs or asks for this
db_password = "MyP@ssw0rd123"
host        = "erp-db.corp.internal"
```

If a user pastes a real credential into the conversation, the agent must:
1. Immediately warn the user that the credential may be exposed
2. Ask them to rotate it
3. Refuse to use or repeat the value — treat it as if it was never provided

**There are no exceptions. Not for debugging, not for "just this once", not for sandbox.**

---

## SEC-01: Secrets via Environment or Key Vault Only

Never hardcode credentials. Use:
- `os.environ['SECRET_NAME']` in Python/PySpark
- `@Microsoft.KeyVault(SecretUri=https://vault.azure.net/secrets/name/version)` in Fabric linked services

Prohibited:
- Passwords in config files
- Connection strings in notebooks
- Tokens in git history

## SEC-02: The Sanitization Barrier

For any source that may contain PII or sensitive data:
1. **Fetch** — pull to RAM only
2. **Sanitize** — apply masking/redaction in RAM  
3. **Write** — only then persist to Delta Lake

Writing raw sensitive data to disk (including /tmp) is a Severity 1 incident.

## SEC-03: Sensitive Field Handling

| Category | Action | Result |
|---|---|---|
| Credit card (PAN) | Mask last 4 | `XXXX-XXXX-XXXX-1234` |
| Passwords / secrets | Drop | `[REDACTED]` |
| API tokens | Redact | `Bearer *****` |
| Names / emails / IDs | Classify and document | Apply masking or pseudonymization per data contract |

## SEC-05: Right to be Forgotten

GDPR/CCPA deletion path must exist for any table storing personal data:
```sql
DELETE FROM silver_users WHERE user_id = '123';
VACUUM silver_users RETAIN 0 HOURS;  -- only for explicit purge
```
Standard VACUUM runs weekly at 168-hour retention.

## SEC-06: Audit Envelope

Every record must carry:
- `_ingest_timestamp` — UTC datetime of ingestion
- `_source_system` — origin identifier
- `_batch_id` — UUID for the pipeline run

## SEC-07: No Raw Logging

Never log full payloads or DataFrames. Prohibited:
```python
print(payload)      # forbidden
df.show()           # forbidden
logging.info(row)   # forbidden if row contains PII
```

## SEC-08: Injection Prevention

Never build Spark SQL or JDBC queries from string concatenation. Use the Column API or parameterized queries.

```python
# ❌ Forbidden
spark.sql(f"SELECT * FROM {table_name} WHERE id = '{user_id}'")

# ✅ Correct
df.filter(F.col("id") == user_id)
spark.sql("SELECT * FROM orders WHERE id = :id", args={"id": user_id})
```

For JDBC sources, use `PreparedStatement`-style patterns and never interpolate external values into query strings.

## SEC-09: Encryption Requirements

- Source connections must use TLS/SSL endpoints — reject plain HTTP
- Never use MD5 or SHA-1 for integrity checks; use SHA-256 or stronger
- Key Vault URIs must use versioned secret references to prevent silent key rotation bypass
- Fabric Lakehouse encryption at rest is platform-managed; confirm it has not been disabled in workspace settings

## SEC-10: Third-Party Dependency Vetting

- Pin all pip installs with version bounds: `%pip install "pkg>=1.0,<2.0"`
- Never install from git URLs, local file paths, or non-PyPI indexes unless approved by operator
- Check new package names for typosquatting before adding them
- No untested packages in production pipelines
- Before adding any new package, verify it has no known CVEs via [osv.dev](https://osv.dev) or NVD

## SEC-11: Data Inventory Maintenance

`memory/platform.md` must list every lakehouse, table, source system, and its sensitivity classification. Update after every pipeline creation, deletion, or schema change. An unmapped table is an unmanaged risk.

## SEC-12: Software Bill of Materials and Supply Chain Integrity

A03:2025 Software Supply Chain Failures applies to every notebook that installs packages at runtime.

- Maintain `memory/sbom.md` listing every `%pip install` package across all notebooks with its pinned version bounds and the notebook(s) that use it
- Update `memory/sbom.md` whenever a package is added, removed, or version-bumped
- Remove unused packages from notebook pip cells — each extra package is additional attack surface
- Do not pin to a version that has a known CVE; check osv.dev before bumping any version bound
- Transitive dependencies of high-risk packages (network I/O, crypto, serialisation) require operator awareness even if not directly imported
