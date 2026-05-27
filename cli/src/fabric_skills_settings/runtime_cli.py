"""`fabric-vibe` - package-owned runtime proxy.

Single Typer dispatcher that subprocess-calls helpers bundled in the installed
package. Each subcommand passes trailing argv through to the underlying script
unchanged. The CWD is preserved, so users run `fabric-vibe ...` from inside
their project repo.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

from . import __version__
from .core.paths import setup_root, tools_root
from .core.version_check import update_notice
from .logging_config import setup_logging

app = typer.Typer(
    name="fabric-vibe",
    help="Run package-owned Fabric helpers for the current target repo.",
    add_completion=False,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

notebook_app  = typer.Typer(no_args_is_help=True, help="Notebook lifecycle helpers.")
pipeline_app  = typer.Typer(no_args_is_help=True, help="Data Factory pipeline helpers.")
lakehouse_app = typer.Typer(no_args_is_help=True, help="Lakehouse inspection helpers.")
workspace_app = typer.Typer(no_args_is_help=True, help="Workspace registry helpers.")
auth_app      = typer.Typer(no_args_is_help=True, help="Authentication helpers.")

app.add_typer(notebook_app,  name="notebook")
app.add_typer(pipeline_app,  name="pipeline")
app.add_typer(lakehouse_app, name="lakehouse")
app.add_typer(workspace_app, name="workspace")
app.add_typer(auth_app,      name="auth")

_IS_WINDOWS = platform.system() == "Windows"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"fabric-vibe {__version__}")
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
    if not quiet:
        notice = update_notice(__version__)
        if notice:
            typer.secho(notice, fg=typer.colors.YELLOW, err=True)


def _require_tool_script(rel: Path) -> Path:
    script = tools_root() / rel
    if not script.exists():
        raise typer.BadParameter(f"packaged helper missing: {rel}")
    return script


def _require_setup_script(name: str) -> Path:
    script = setup_root() / name
    if not script.exists():
        raise typer.BadParameter(f"packaged setup helper missing: {name}")
    return script


def _dispatch_python(script: Path, extra: list[str]) -> int:
    return subprocess.run([sys.executable, str(script), *extra]).returncode


def _dispatch_shell(posix_rel: Path, windows_rel: Path, extra: list[str]) -> int:
    if _IS_WINDOWS:
        script = _require_tool_script(windows_rel)
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), *extra]
    else:
        script = _require_tool_script(posix_rel)
        cmd = ["bash", str(script), *extra]
    return subprocess.run(cmd).returncode


def _dispatch_setup(extra: list[str]) -> int:
    if _IS_WINDOWS:
        script = _require_setup_script("setup.ps1")
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), *extra]
    else:
        script = _require_setup_script("setup.sh")
        cmd = ["bash", str(script), *extra]
    return subprocess.run(cmd).returncode


_PASSTHROUGH_CONTEXT = {
    "allow_extra_args": True,
    "ignore_unknown_options": True,
    "help_option_names": ["-h", "--help"],
}


@notebook_app.command("build", context_settings=_PASSTHROUGH_CONTEXT)
def notebook_build(ctx: typer.Context) -> None:
    """Build .Notebook bundles from workspace/<topic>/<name>.py."""
    script = _require_tool_script(Path("notebook/build.py"))
    raise typer.Exit(code=_dispatch_python(script, ctx.args))


@notebook_app.command("deploy", context_settings=_PASSTHROUGH_CONTEXT)
def notebook_deploy(ctx: typer.Context) -> None:
    """Deploy, run, monitor, and fetch notebooks."""
    script = _require_tool_script(Path("notebook/deploy.py"))
    raise typer.Exit(code=_dispatch_python(script, ctx.args))


@notebook_app.command("smoke-test", context_settings=_PASSTHROUGH_CONTEXT)
def notebook_smoke_test(ctx: typer.Context) -> None:
    """Run the notebook smoke-test script."""
    rc = _dispatch_shell(
        posix_rel=Path("notebook/smoke-test.sh"),
        windows_rel=Path("notebook/smoke-test.ps1"),
        extra=ctx.args,
    )
    raise typer.Exit(code=rc)


@pipeline_app.command("manage", context_settings=_PASSTHROUGH_CONTEXT)
def pipeline_manage(ctx: typer.Context) -> None:
    """Create, run, list, and test Data Factory pipelines."""
    script = _require_tool_script(Path("pipeline/manage.py"))
    raise typer.Exit(code=_dispatch_python(script, ctx.args))


@lakehouse_app.command("list-tables", context_settings=_PASSTHROUGH_CONTEXT)
def lakehouse_list_tables(ctx: typer.Context) -> None:
    """Inspect lakehouse tables and schemas."""
    script = _require_tool_script(Path("lakehouse/list-tables.py"))
    raise typer.Exit(code=_dispatch_python(script, ctx.args))


@workspace_app.command("init", context_settings=_PASSTHROUGH_CONTEXT)
def workspace_init(ctx: typer.Context) -> None:
    """Populate workspaces.json from the Fabric API."""
    script = _require_tool_script(Path("workspace/init.py"))
    raise typer.Exit(code=_dispatch_python(script, ctx.args))


@workspace_app.command("switch", context_settings=_PASSTHROUGH_CONTEXT)
def workspace_switch(ctx: typer.Context) -> None:
    """Switch the active workspace and refresh per-resource env keys."""
    script = _require_tool_script(Path("workspace/switch.py"))
    raise typer.Exit(code=_dispatch_python(script, ctx.args))


@workspace_app.command("transfer", context_settings=_PASSTHROUGH_CONTEXT)
def workspace_transfer(ctx: typer.Context) -> None:
    """Transfer items between workspaces."""
    script = _require_tool_script(Path("workspace/transfer.py"))
    raise typer.Exit(code=_dispatch_python(script, ctx.args))


@workspace_app.command("pick", context_settings=_PASSTHROUGH_CONTEXT)
def workspace_pick(ctx: typer.Context) -> None:
    """Interactive active-workspace picker."""
    script = _require_tool_script(Path("workspace/pick.py"))
    raise typer.Exit(code=_dispatch_python(script, ctx.args))


@app.command("lint", context_settings=_PASSTHROUGH_CONTEXT)
def lint(ctx: typer.Context) -> None:
    """Run deterministic lints."""
    script = _require_tool_script(Path("lint/__main__.py"))
    raise typer.Exit(code=_dispatch_python(script, ctx.args))


@app.command("precommit", context_settings=_PASSTHROUGH_CONTEXT)
def precommit(ctx: typer.Context) -> None:
    """Run the aggregate pre-commit check."""
    rc = _dispatch_shell(
        posix_rel=Path("precommit/pre-commit-check.sh"),
        windows_rel=Path("precommit/pre-commit-check.ps1"),
        extra=ctx.args,
    )
    raise typer.Exit(code=rc)


@auth_app.command("refresh", context_settings=_PASSTHROUGH_CONTEXT)
def auth_refresh(ctx: typer.Context) -> None:
    """Generate the MCP identity key, sign your email, and update MCP configs."""
    script = _require_tool_script(Path("auth/refresh.py"))
    raise typer.Exit(code=_dispatch_python(script, ctx.args))


@app.command("setup", context_settings=_PASSTHROUGH_CONTEXT)
def setup(ctx: typer.Context) -> None:
    """Run the target bootstrap from the current repo root."""
    raise typer.Exit(code=_dispatch_setup(ctx.args))
