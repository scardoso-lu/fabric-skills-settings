"""Phase P5.5+P5.6: TDD coverage for skill splits.

Long skills (>150 lines) split into sections/<slug>.md must:
1. preserve the original H2 headings as discoverable section nodes
2. surface every section in <= 2 hops from graph-content/indexes/skills-index
3. keep the parent SKILL.md as a thin index node

Currently only fabric-notebook-loop is split. Other long skills follow in
follow-up commits; the test loop is structured so adding a new entry to
SPLIT_SKILLS extends coverage without rewriting test logic.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

SPLIT_SKILLS: dict[str, dict[str, list[str]]] = {
    "fabric-notebook-loop": {
        "expected_sections": [
            "must",
            "prefer-avoid",
            "the-loop",
            "diagnosing-opaque-failures",
            "mlflow-platform-limits",
            "full-example",
        ],
        "original_h2_headings": [
            "MUST",
            "PREFER",
            "AVOID",
            "The Loop",
            "Cell Structure",
            "Run Status Interpretation",
            "Diagnosing Opaque Smoke-test Failures",
            "MLflow in Fabric — Platform Limits",
            "Full Example: CSV to Bronze",
        ],
    },
}


def _build_graph_into_temp(tmp_path: Path) -> None:
    """Run bin/build-graph.py with --out / --bm25 pointed at tmp_path to keep tests hermetic."""
    out = tmp_path / "graph.json"
    bm25 = tmp_path / "bm25.pkl"
    subprocess.run(
        [sys.executable, str(ROOT / "bin" / "build-graph.py"),
         "--root", str(ROOT), "--out", str(out), "--bm25", str(bm25)],
        check=True, capture_output=True,
    )


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    sys.path.insert(0, str(ROOT / "tool"))
    from graph.store import GraphStore
    tmp = tmp_path_factory.mktemp("graph")
    _build_graph_into_temp(tmp)
    return GraphStore.load(tmp / "graph.json")


@pytest.mark.parametrize("skill,spec", list(SPLIT_SKILLS.items()))
def test_skill_parent_is_thin_index(skill: str, spec: dict, store):
    """The parent SKILL.md must shrink — fewer lines than the original (which was > 150)
    and must list its sections as curated outbound links."""
    path = ROOT / "profiles" / "skills" / skill / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    line_count = text.count("\n")
    assert line_count < 60, f"{skill}/SKILL.md is now {line_count} lines; expected < 60 after split"
    parent_id = f"skills/{skill}"
    assert store.has_node(parent_id), f"{parent_id} missing from graph"
    successors = set(store.graph.successors(parent_id))
    for section in spec["expected_sections"]:
        section_id = f"skills/{skill}/{section}"
        assert section_id in successors, (
            f"parent {parent_id} must curate-link to {section_id}; "
            f"actual outbound: {sorted(successors)}"
        )


@pytest.mark.parametrize("skill,spec", list(SPLIT_SKILLS.items()))
def test_section_files_exist_and_have_frontmatter(skill: str, spec: dict, store):
    sections_dir = ROOT / "profiles" / "skills" / skill / "sections"
    for section in spec["expected_sections"]:
        path = sections_dir / f"{section}.md"
        assert path.exists(), f"missing section file: {path.relative_to(ROOT)}"
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{path.name} must start with YAML frontmatter"
        assert f"skills/{skill}" in text, f"{path.name} must link back to parent skill"


@pytest.mark.parametrize("skill,spec", list(SPLIT_SKILLS.items()))
def test_original_h2_content_preserved_across_split(skill: str, spec: dict):
    """Union of section bodies must contain every original H2 heading (verbatim)."""
    sections_dir = ROOT / "profiles" / "skills" / skill / "sections"
    union = "\n".join(
        p.read_text(encoding="utf-8") for p in sections_dir.glob("*.md")
    )
    for heading in spec["original_h2_headings"]:
        pattern = rf"^#{{1,2}}\s+{re.escape(heading)}\s*$"
        assert re.search(pattern, union, re.MULTILINE), (
            f"H2 heading {heading!r} from the pre-split SKILL.md is missing from any section"
        )


@pytest.mark.parametrize("skill,spec", list(SPLIT_SKILLS.items()))
def test_section_nodes_reachable_within_two_hops_from_skills_index(skill: str, spec: dict, store):
    import networkx as nx

    for section in spec["expected_sections"]:
        section_id = f"skills/{skill}/{section}"
        assert store.has_node(section_id), f"{section_id} missing from graph"
        hops = nx.shortest_path_length(
            store.graph, "graph-content/indexes/skills-index", section_id
        )
        assert hops <= 2, (
            f"{section_id} is {hops} hops from skills-index; target <= 2"
        )
