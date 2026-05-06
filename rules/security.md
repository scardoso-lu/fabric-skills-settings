# Security Rules

These rules apply to all agents and all pipelines. They are non-negotiable.

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

## SEC-04: Sandbox Boundary

All agent work happens in sandbox/dev workspace. Production connections require:
- Explicit operator approval
- Service principal authentication (no personal credentials)
- Runbook documenting the change

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
df.show()           # forbidden in production
logging.info(row)   # forbidden if row contains PII
```
