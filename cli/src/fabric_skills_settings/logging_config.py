"""Logging setup for the CLI.

Uses Rich for pretty terminal output while keeping logger names available for
filtering. `setup_logging(verbose=True)` enables debug-level output.
"""

from __future__ import annotations

import logging

from rich.console import Console
from rich.logging import RichHandler

_console = Console(stderr=True, highlight=False)


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    handler = RichHandler(
        console=_console,
        show_time=False,
        show_path=False,
        show_level=verbose,
        markup=True,
        rich_tracebacks=True,
    )
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[handler],
        force=True,
    )


def get_console() -> Console:
    return _console
