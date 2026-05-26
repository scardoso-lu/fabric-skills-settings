"""`fabric-agents install` — write profile/scaffold/tool files into a target repo."""

from __future__ import annotations

import logging

from ..core.bootstrap import bootstrap_target
from ..core.files import WriteOptions
from ._common import apply_profile_set, resolve_target

log = logging.getLogger(__name__)


def run(
    *,
    profile: str,
    target: str,
    dry_run: bool = False,
    force: bool = False,
    backup: bool = False,
    no_bootstrap: bool = False,
    self_test: bool = False,
) -> int:
    target_path = resolve_target(target, allow_package_dir=self_test)
    options = WriteOptions(dry_run=dry_run, check=False, force=force, backup=backup)

    operations, _ = apply_profile_set(target_path, profile, options)
    for op in operations:
        log.info(op)

    if dry_run or no_bootstrap:
        return 0

    rc = bootstrap_target(target_path)
    return rc
