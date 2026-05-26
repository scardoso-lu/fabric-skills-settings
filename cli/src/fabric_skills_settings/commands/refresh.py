"""`fabric-agents refresh` — re-copy managed files without re-running bootstrap.

Equivalent to `install --no-bootstrap`, but documents intent: use this after a
package upgrade to pick up updates to managed files in an existing target.
"""

from __future__ import annotations

from . import install


def run(
    *,
    profile: str,
    target: str,
    dry_run: bool = False,
    force: bool = False,
    backup: bool = False,
    self_test: bool = False,
) -> int:
    return install.run(
        profile=profile,
        target=target,
        dry_run=dry_run,
        force=force,
        backup=backup,
        no_bootstrap=True,
        self_test=self_test,
    )
