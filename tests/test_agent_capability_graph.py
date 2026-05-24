"""Derived agent-capability graph tests."""

from __future__ import annotations

from pathlib import Path

from graph_build.agent_capabilities import build_agent_capability_graph
from graph.schema import Edge, Node
from graph.store import GraphStore


def _node(node_id: str, title: str, description: str = "", kind: str = "content") -> Node:
    return Node(
        id=node_id,
        path=f"memory/{node_id}.md",
        title=title,
        description=description,
        kind=kind,
        frontmatter={},
        mtime=1.0,
    )


def _knowledge() -> GraphStore:
    store = GraphStore()
    store.add_node(_node("skills/fabric-ingest", "Ingest skill", kind="skill"))
    store.add_node(_node("skills/fabric-validate", "Validate skill", kind="skill"))
    store.add_node(_node("rules/data-engineering", "Data engineering rules", kind="rule"))
    store.add_node(_node("rules/security", "Security rules", kind="rule"))
    store.add_node(_node("graph-content/session/session-start", "Session start"))
    return store


AGENT_FRONTMATTER = {
    "orchestrator": """---
name: orchestrator
links:
  - graph-content/session/session-start
skills:
  - prd
---
""",
    "developer": """---
name: developer
links:
  - skills/fabric-ingest
  - rules/data-engineering
skills:
  - fabric-ingest
---
""",
    "tester": """---
name: tester
links:
  - skills/fabric-validate
skills:
  - fabric-validate
---
""",
    "operator": """---
name: operator
links:
  - rules/security
---
""",
}


def test_capability_graph_only_includes_referenced_nodes(tmp_path):
    _write_native_agents(tmp_path, AGENT_FRONTMATTER)
    result = build_agent_capability_graph(_knowledge(), tmp_path)

    assert result.store.kinds()["capability"] == 4
    assert result.store.has_node("skills/fabric-ingest")
    assert result.store.has_node("skills/fabric-validate")
    assert result.store.has_node("rules/security")
    assert result.store.has_node("graph-content/session/session-start")


def test_capability_edges_come_from_agent_frontmatter(tmp_path):
    _write_native_agents(tmp_path, AGENT_FRONTMATTER)
    result = build_agent_capability_graph(_knowledge(), tmp_path)
    edges = {(src, dst): data["kind"] for src, dst, data in result.store.graph.edges(data=True)}

    assert edges[("capabilities/orchestrator", "capabilities/developer")] == "capability-route"
    assert edges[("capabilities/orchestrator", "capabilities/tester")] == "capability-route"
    assert edges[("capabilities/orchestrator", "capabilities/operator")] == "capability-route"
    assert edges[("capabilities/developer", "capabilities/orchestrator")] == "capability-route"

    assert edges[("capabilities/developer", "skills/fabric-ingest")] == "capability-covers"
    assert edges[("capabilities/developer", "rules/data-engineering")] == "capability-covers"
    assert edges[("capabilities/tester", "skills/fabric-validate")] == "capability-covers"
    assert edges[("capabilities/operator", "rules/security")] == "capability-covers"

    assert ("capabilities/developer", "skills/fabric-validate") not in edges
    assert ("capabilities/operator", "skills/fabric-ingest") not in edges


def test_unknown_reference_emits_warning_not_silent_drop(tmp_path):
    frontmatter = dict(AGENT_FRONTMATTER)
    frontmatter["developer"] = """---
name: developer
links:
  - skills/does-not-exist
---
"""
    _write_native_agents(tmp_path, frontmatter)
    result = build_agent_capability_graph(_knowledge(), tmp_path)

    assert any("skills/does-not-exist" in w for w in result.warnings)


def test_warns_when_native_agent_file_missing(tmp_path):
    (tmp_path / "profiles" / "codex" / "agents").mkdir(parents=True)
    (tmp_path / "profiles" / "codex" / "agents" / "developer.toml").write_text("", encoding="utf-8")

    result = build_agent_capability_graph(_knowledge(), tmp_path)

    assert result.store.get_node("capabilities/developer").frontmatter["agents"] == ["developer"]
    assert any("capabilities/tester" in w for w in result.warnings)


def _write_native_agents(root: Path, frontmatter: dict[str, str]) -> None:
    codex = root / "profiles" / "codex" / "agents"
    claude = root / "profiles" / "claude" / "agents"
    codex.mkdir(parents=True, exist_ok=True)
    claude.mkdir(parents=True, exist_ok=True)
    for name, fm in frontmatter.items():
        (claude / f"{name}.md").write_text(fm + f"\n# {name}\n", encoding="utf-8")
        (codex / f"{name}.toml").write_text(f'name = "{name}"\n', encoding="utf-8")
