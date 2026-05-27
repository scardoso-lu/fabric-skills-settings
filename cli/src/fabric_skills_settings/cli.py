"""Typer CLI for fabric-vibecoding-settings.

Exposes three subcommands:

    fabric-vibecoding-agents install --profile claude --target /path/to/repo
    fabric-vibecoding-agents check   --profile claude --target /path/to/repo
    fabric-vibecoding-agents refresh --profile claude --target /path/to/repo
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

import typer

from . import __version__
from .commands import check as check_cmd
from .commands import install as install_cmd
from .commands import refresh as refresh_cmd
from .core.version_check import update_notice
from .logging_config import setup_logging


class Profile(str, Enum):
    codex = "codex"
    claude = "claude"
    all = "all"

app = typer.Typer(
    name="fabric-vibecoding-agents",
    help="Install Microsoft Fabric agent profiles (Claude Code and Codex) into a target repository.",
    add_completion=False,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


ProfileOption = Annotated[
    Profile,
    typer.Option(
        "--profile", "-p",
        help="Agent profile to install: codex, claude, or all.",
        case_sensitive=False,
    ),
]
TargetOption = Annotated[
    str | None,
    typer.Option("--target", "-t", help="Target git repository path. Defaults to current directory."),
]
DryRunOption = Annotated[
    bool,
    typer.Option("--dry-run", help="Print planned changes without writing."),
]
ForceOption = Annotated[
    bool,
    typer.Option("--force", help="Overwrite non-managed existing files."),
]
BackupOption = Annotated[
    bool,
    typer.Option("--backup", help="Back up replaced files alongside the originals."),
]
NoBootstrapOption = Annotated[
    bool,
    typer.Option(
        "--no-bootstrap",
        help="Skip the post-install bootstrap (fabric-vibe setup).",
    ),
]
SelfTestOption = Annotated[
    bool,
    typer.Option(
        "--self-test",
        help="Allow targeting the package install directory (testing only).",
        hidden=True,
    ),
]
VerboseOption = Annotated[
    bool,
    typer.Option("--verbose", "-v", help="Enable debug-level logging."),
]
QuietOption = Annotated[
    bool,
    typer.Option("--quiet", "-q", help="Suppress info-level logging."),
]


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"fabric-vibecoding-agents {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version and exit."),
    ] = False,
    verbose: VerboseOption = False,
    quiet: QuietOption = False,
) -> None:
    setup_logging(verbose=verbose, quiet=quiet)
    if not quiet:
        notice = update_notice(__version__)
        if notice:
            typer.secho(notice, fg=typer.colors.YELLOW, err=True)


@app.command()
def install(
    profile: ProfileOption,
    target: TargetOption = None,
    dry_run: DryRunOption = False,
    force: ForceOption = False,
    backup: BackupOption = False,
    no_bootstrap: NoBootstrapOption = False,
    self_test: SelfTestOption = False,
) -> None:
    """Install profile and scaffold files into a target repo."""
    rc = install_cmd.run(
        profile=profile.value,
        target=target,
        dry_run=dry_run,
        force=force,
        backup=backup,
        no_bootstrap=no_bootstrap,
        self_test=self_test,
    )
    raise typer.Exit(code=rc)


@app.command()
def check(
    profile: ProfileOption,
    target: TargetOption = None,
    self_test: SelfTestOption = False,
) -> None:
    """Verify target state; exit 1 on drift, 0 on match."""
    rc = check_cmd.run(profile=profile.value, target=target, self_test=self_test)
    raise typer.Exit(code=rc)


@app.command()
def refresh(
    profile: ProfileOption,
    target: TargetOption = None,
    dry_run: DryRunOption = False,
    force: ForceOption = False,
    backup: BackupOption = False,
    self_test: SelfTestOption = False,
) -> None:
    """Re-copy managed files without re-running the target bootstrap."""
    rc = refresh_cmd.run(
        profile=profile.value,
        target=target,
        dry_run=dry_run,
        force=force,
        backup=backup,
        self_test=self_test,
    )
    raise typer.Exit(code=rc)
