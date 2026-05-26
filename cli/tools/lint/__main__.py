#!/usr/bin/env python3
"""Run every registered lint against the target repo.

Usage:
    python -m tool.lint                       # scan repo containing this script
    python -m tool.lint --target /path/to/repo
    python tool/lint/__main__.py --target .

Exit codes:
    0  no errors (warnings are reported but don't fail)
    1  one or more rule violations with severity == "error"
    2  bad CLI usage
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a script (``python tool/lint/__main__.py``) without
# requiring the package to be on sys.path.
if __package__ is None or __package__ == "":  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tool.lint import LINTS  # noqa: E402
from tool.lint.core import emit_report, run_all  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repo root to scan (default: parent of tool/)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = args.target.resolve()
    findings, code = run_all(LINTS, target)
    emit_report(findings, target)
    return code


if __name__ == "__main__":
    sys.exit(main())
