"""SEC-01: forbid hardcoded credentials in notebook source.

This is the **regex-based lint template**. New regex lints should copy this
shape:
  - module-level ``PATTERNS`` list of compiled regexes + per-pattern messages
  - ``run(target_root)`` walks every .py file under SCAN_ROOTS and reports
    findings.

What we flag:
  - JWT-ish tokens             (``eyJ`` + 20+ base64url chars)
  - Azure Storage account keys (``AccountKey=`` + base64)
  - SAS tokens                  (``SharedAccessSignature=``)
  - Bearer tokens               (``Bearer `` + 20+ token chars)
  - Inline ``password = "..."`` assignments where the value is not an
    ``os.environ`` lookup
  - Connection strings with embedded passwords (``Pwd=``, ``Password=``)

What we don't flag (intentional):
  - ``os.environ["..."]`` lookups
  - ``# %% [contract]`` / ``# %% [parameters]`` cells (declarative, not
    runtime)
  - ``.env.example`` style placeholders (``<...>``, ``REPLACE_ME``)
"""

from __future__ import annotations

import re
from pathlib import Path

from .core import LintFinding, SCAN_ROOTS, iter_py_files


# (compiled regex, short message). One pattern per known leakage shape.
PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
        "JWT-shaped token literal — use os.environ[...] and load from .env",
    ),
    (
        re.compile(r"AccountKey=[A-Za-z0-9+/=]{20,}"),
        "Azure storage AccountKey literal — use Key Vault secret reference",
    ),
    (
        re.compile(r"SharedAccessSignature=[A-Za-z0-9%]{20,}"),
        "SAS token literal — use Key Vault secret reference",
    ),
    (
        re.compile(r'Bearer\s+[A-Za-z0-9_\-\.]{20,}'),
        "Bearer token literal — load token from os.environ",
    ),
    (
        re.compile(r'(?i)\b(password|pwd|secret|api[_-]?key|token)\s*=\s*[\'"](?!<|REPLACE_ME)[^\'"\s]{6,}[\'"]'),
        "hardcoded credential assignment — use os.environ[...] instead",
    ),
    (
        re.compile(r'(?i)(Pwd|Password)=[^;\s\'"]{4,}'),
        "connection string with embedded password — use Key Vault reference",
    ),
]

# Lines containing these substrings are treated as legitimate (the literal
# is a placeholder or a regex source, not a real credential).
ALLOW_SUBSTRINGS = (
    "os.environ",
    "Key Vault",
    "REPLACE_ME",
    "<your-",
    "<fill",
    "EXAMPLE_",
    ".env.example",
    # The lint module itself contains the patterns as string literals.
    "tool/lint/sec_no_hardcoded_secrets",
)


def run(target_root: Path) -> list[LintFinding]:
    findings: list[LintFinding] = []
    for scan_root in SCAN_ROOTS:
        root = target_root / scan_root
        for py in iter_py_files(root):
            try:
                text = py.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if any(allow in line for allow in ALLOW_SUBSTRINGS):
                    continue
                for pat, msg in PATTERNS:
                    if pat.search(line):
                        findings.append(
                            LintFinding(
                                rule_id="SEC-01",
                                path=py,
                                line=lineno,
                                msg=msg,
                            )
                        )
                        break  # one finding per line is enough
    return findings
