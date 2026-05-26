"""`fabric-agents check` — verify a target repo matches the package state."""

from __future__ import annotations

import logging

from ..core.files import WriteOptions
from ._common import apply_profile_set, resolve_target

log = logging.getLogger(__name__)


def run(*, profile: str, target: str, self_test: bool = False) -> int:
    target_path = resolve_target(target, allow_package_dir=self_test)
    options = WriteOptions(check=True)

    operations, _ = apply_profile_set(target_path, profile, options)
    for op in operations:
        log.info(op)

    if any(op.startswith(("MISSING", "DIFF", "OBSOLETE")) for op in operations):
        return 1
    return 0
