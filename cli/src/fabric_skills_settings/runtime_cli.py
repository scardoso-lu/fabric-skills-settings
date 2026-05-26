"""`fabric-cli` — target-side runtime proxy.

Single Typer dispatcher that subprocess-calls the scripts shipped into a
target repo's `tool/` directory. Each subcommand passes its trailing argv
through to the underlying script unchanged. The CWD is preserved, so users
run `fabric-cli ...` from inside their project repo.

Subcommands:
    fabric-cli notebook build  [args]
    fabric-cli notebook deploy [args]
    fabric-cli notebook smoke-test [args]
    fabric-cli pipeline  manage  [args]
    fabric-cli lakehouse list-tables [args]
    fabric-cli workspace init|switch|transfer|pick [args]
    fabric-cli lint      [args]
    fabric-cli precommit
"""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

from . import __version__
from .logging_config import setup_logging

app = typer.Typer(
    name="fabric-cli",
    help="Run target-repo helpers under tool/ — notebook, pipeline, lakehouse, workspace, lint, precommit.",
    add_completion=False,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

notebook_app  = typer.Typer(no_args_is_help=True, help="Notebook lifecycle helpers.")
pipeline_app  = typer.Typer(no_args_is_help=True, help="Data Factory pipeline helpers.")
lakehouse_app = typer.Typer(no_args_is_help=True, help="Lakehouse inspection helpers.")
workspace_app = typer.Typer(no_args_is_help=True, help="Workspace registry helpers.")

app.add_typer(notebook_app,  name="notebook")
app.add_typer(pipeline_app,  name="pipeline")
app.add_typer(lakehouse_app, name="lakehouse")
app.add_typer(workspace_app, name="workspace")


_IS_WINDOWS = platform.system() == "Windows"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"fabric-cli {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version and exit."),
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Debug-level logging.")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info logging.")] = False,
) -> None:
    setup_logging(verbose=verbose, quiet=quiet)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _require_target_script(rel: Path) -> Path:
    """Resolve a path under the current working directory and require it exist."""
    script = Path.cwd() / rel
    if not script.exists():
        raise typer.BadParameter(
            f"{rel} not found relative to the current directory. "
            "Run fabric-cli from your target repo root (where `tool/` lives)."
        )
    return script


def _dispatch_python(script: Path, extra: list[str]) -> int:
    cmd = [sys.executable, str(script), *extra]
    return subprocess.run(cmd).returncode


def _dispatch_module(module: str, extra: list[str]) -> int:
    cmd = [sys.executable, "-m", module, *extra]
    return subprocess.run(cmd).returncode


def _dispatch_shell(posix_rel: Path, windows_rel: Path, extra: list[str]) -> int:
    if _IS_WINDOWS:
        script = _require_target_script(windows_rel)
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), *extra]
    else:
        script = _require_target_script(posix_rel)
        cmd = ["bash", str(script), *extra]
    return subprocess.run(cmd).returncode


_PASSTHROUGH_CONTEXT = {
    "allow_extra_args": True,
    "ignore_unknown_options": True,
    "help_option_names": ["-h", "--help"],
}


# ── notebook ─────────────────────────────────────────────────────────────────

@notebook_app.command("build", context_settings=_PASSTHROUGH_CONTEXT)
def notebook_build(ctx: typer.Context) -> None:
    """Build .Notebook bundles from workspace/<topic>/<name>.py."""
    script = _require_target_script(Path("tool/notebook/build.py"))
    raise typer.Exit(code=_dispatch_python(script, ctx.args))


@notebook_app.command("deploy", context_settings=_PASSTHROUGH_CONTEXT)
def notebook_deploy(ctx: typer.Context) -> None:
    """Deploy, run, monitor, and fetch notebooks."""
    script = _require_target_script(Path("tool/notebook/deploy.py"))
    raise typer.Exit(code=_dispatch_python(script, ctx.args))


@notebook_app.command("smoke-test", context_settings=_PASSTHROUGH_CONTEXT)
def notebook_smoke_test(ctx: typer.Context) -> None:
    """Run the notebook smoke-test script (bash on POSIX, PowerShell on Windows)."""
    rc = _dispatch_shell(
        posix_rel=Path("tool/notebook/smoke-test.sh"),
        windows_rel=Path("tool/notebook/smoke-test.ps1"),
        extra=ctx.args,
    )
    raise typer.Exit(code=rc)


# ── pipeline ─────────────────────────────────────────────────────────────────

@pipeline_app.command("manage", context_settings=_PASSTHROUGH_CONTEXT)
def pipeline_manage(ctx: typer.Context) -> None:
    """Create, run, list, and test Data Factory pipelines."""
    script = _require_target_script(Path("tool/pipeline/manage.py"))
    raise typer.Exit(code=_dispatch_python(script, ctx.args))


# ── lakehouse ────────────────────────────────────────────────────────────────

@lakehouse_app.command("list-tables", context_settings=_PASSTHROUGH_CONTEXT)
def lakehouse_list_tables(ctx: typer.Context) -> None:
    """Inspect lakehouse tables and schemas."""
    script = _require_target_script(Path("tool/lakehouse/list-tables.py"))
    raise typer.Exit(code=_dispatch_python(script, ctx.args))


# ── workspace ────────────────────────────────────────────────────────────────

@workspace_app.command("init", context_settings=_PASSTHROUGH_CONTEXT)
def workspace_init(ctx: typer.Context) -> None:
    """Populate workspaces.json from the Fabric API."""
    script = _require_target_script(Path("tool/workspace/init.py"))
    raise typer.Exit(code=_dispatch_python(script, ctx.args))


@workspace_app.command("switch", context_settings=_PASSTHROUGH_CONTEXT)
def workspace_switch(ctx: typer.Context) -> None:
    """Switch the active workspace and refresh per-resource env keys."""
    script = _require_target_script(Path("tool/workspace/switch.py"))
    raise typer.Exit(code=_dispatch_python(script, ctx.args))


@workspace_app.command("transfer", context_settings=_PASSTHROUGH_CONTEXT)
def workspace_transfer(ctx: typer.Context) -> None:
    """Transfer items between workspaces."""
    script = _require_target_script(Path("tool/workspace/transfer.py"))
    raise typer.Exit(code=_dispatch_python(script, ctx.args))


@workspace_app.command("pick", context_settings=_PASSTHROUGH_CONTEXT)
def workspace_pick(ctx: typer.Context) -> None:
    """Interactive active-workspace picker."""
    script = _require_target_script(Path("tool/workspace/pick.py"))
    raise typer.Exit(code=_dispatch_python(script, ctx.args))


# ── lint / precommit ─────────────────────────────────────────────────────────

@app.command("lint", context_settings=_PASSTHROUGH_CONTEXT)
def lint(ctx: typer.Context) -> None:
    """Run deterministic lints (SEC-01 hardcoded secrets, DE-09 Faker seed)."""
    # Use module form — tool/lint/__main__.py provides the entry point.
    if not (Path.cwd() / "tool" / "lint" / "__main__.py").exists():
        raise typer.BadParameter("tool/lint not found in CWD — run from target repo root.")
    raise typer.Exit(code=_dispatch_module("tool.lint", ctx.args))


@app.command("precommit", context_settings=_PASSTHROUGH_CONTEXT)
def precommit(ctx: typer.Context) -> None:
    """Run the aggregate pre-commit check (lint + checks)."""
    rc = _dispatch_shell(
        posix_rel=Path("tool/precommit/pre-commit-check.sh"),
        windows_rel=Path("tool/precommit/pre-commit-check.ps1"),
        extra=ctx.args,
    )
    raise typer.Exit(code=rc)
