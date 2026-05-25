"""Layout assertions driving the folder redesign.

Each xfail-marked test guards a post-move invariant. Migration steps un-xfail
them one block at a time; CI is green when every block is un-xfail and passing.
See: C:\\Users\\User\\.claude\\plans\\plan-a-folder-redesing-giggly-marble.md
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# ── Step 1: bin/ + build/ → packaging/ ────────────────────────────────────────
def test_packaging_dir_exists():
    assert (ROOT / "packaging").is_dir()


def test_packaging_has_install_cli():
    assert (ROOT / "packaging" / "install-fabric-agent").is_file()


def test_packaging_builders_present():
    builders = ROOT / "packaging" / "builders"
    assert (builders / "build-graph.py").is_file()
    assert (builders / "build-agent-capability-graph.py").is_file()
    assert (builders / "graph_build" / "visualize.py").is_file()


def test_packaging_validators_present():
    validators = ROOT / "packaging" / "validators"
    assert (validators / "validate-install-package.py").is_file()
    assert (validators / "validate-agent-guidance.py").is_file()


def test_bin_and_build_removed():
    assert not (ROOT / "bin").exists()
    assert not (ROOT / "build").exists()


# ── Step 2: fabric_agent_installer/ → packaging/fabric_agent_installer/ ───────
def test_installer_package_under_packaging():
    pkg = ROOT / "packaging" / "fabric_agent_installer"
    assert (pkg / "__init__.py").is_file()
    assert (pkg / "_installer.py").is_file()
    assert not (ROOT / "fabric_agent_installer").exists()


# ── Step 3: rules/ + graph-content/ → content/ ───────────────────────────────
def test_content_dir_exists():
    assert (ROOT / "content" / "rules").is_dir()
    assert (ROOT / "content" / "graph-content").is_dir()
    assert (ROOT / "content" / "rules" / "security.md").is_file()
    assert (ROOT / "content" / "graph-content" / "entry.md").is_file()


def test_legacy_content_roots_removed():
    assert not (ROOT / "rules").exists()
    assert not (ROOT / "profiles" / "shared" / "graph-content").exists()


# ── Step 4: project-layout/tool/ deleted; project-layout/ → scaffold/ ────────
def test_project_layout_replaced_by_scaffold():
    assert not (ROOT / "profiles" / "shared" / "project-layout").exists()
    assert (ROOT / "profiles" / "shared" / "scaffold").is_dir()
    # The tool/ mirror is gone; root tool/ is the single source.
    scaffold_tool = ROOT / "profiles" / "shared" / "scaffold" / "tool"
    if scaffold_tool.exists():
        # If anything under scaffold/tool/ remains, it must be scaffold-only (e.g. a target-side setup wrapper),
        # never a mirror of root tool/ runtime code.
        for child in scaffold_tool.iterdir():
            assert child.name == "setup", (
                f"unexpected scaffold tool subdir: {child.name} (only target-side setup wrappers allowed)"
            )


# ── Step 5: tool/mcp/ → mcp/ at root ──────────────────────────────────────────
def test_mcp_dir_at_root():
    assert (ROOT / "mcp" / "server.py").is_file()
    assert (ROOT / "mcp" / "graph-server.py").is_file()
    assert not (ROOT / "tool" / "mcp").exists()


# ── Step 6: memory/.graph/ → dist/.graph/ (source repo only) ──────────────────
def test_dist_graph_replaces_memory_graph():
    assert (ROOT / "dist" / ".graph" / "graph.json").is_file()
    assert (ROOT / "dist" / ".graph" / "graph-bm25.pkl").is_file()
    # Source repo no longer carries memory/ at all.
    assert not (ROOT / "memory").exists()
