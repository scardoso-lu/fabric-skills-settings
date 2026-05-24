"""Builder end-to-end tests over a synthetic markdown tree."""
from __future__ import annotations

from pathlib import Path

from graph.builder import build
from graph.schema import id_from_path, parse_frontmatter


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_tree(root: Path) -> None:
    _write(
        root / "profiles" / "shared" / "graph-content" / "entry.md",
        "---\nname: entry\ndescription: Setup gate\nlinks:\n  - graph-content/session/session-start\n---\n\n# Entry\nSee rules/security.md and skills/fabric-transform.\n",
    )
    _write(
        root / "profiles" / "shared" / "graph-content" / "session" / "session-start.md",
        "---\nname: session-start\ndescription: Read order\n---\n\n# Session start\nWorkflows in profiles/skills/fabric-transform/SKILL.md.\n",
    )
    _write(
        root / "profiles" / "skills" / "fabric-transform" / "SKILL.md",
        "---\nname: fabric-transform\ndescription: Silver/Gold transform skill\nlinks:\n  - rules/data-engineering\n---\n\n# fabric-transform\nMERGE pattern with idempotent upsert.\n",
    )
    _write(
        root / "rules" / "data-engineering.md",
        "---\nname: data-engineering\ndescription: Pipeline rules\n---\n\n# Data engineering rules\nIdempotency required.\n",
    )
    _write(
        root / "rules" / "security.md",
        "---\nname: security\ndescription: Secrets handling rules\n---\n\n# Security\nNever commit credentials.\n",
    )
    _write(
        root / "templates" / "runbook.md",
        "---\nname: runbook\ndescription: Runbook template\n---\n\n# Runbook\n",
    )


def test_build_indexes_expected_nodes(tmp_path):
    _make_tree(tmp_path)
    result = build(tmp_path)
    assert result.errors == []
    ids = set(result.store.graph.nodes)
    assert {
        "graph-content/entry",
        "graph-content/session/session-start",
        "skills/fabric-transform",
        "rules/data-engineering",
        "rules/security",
        "templates/runbook",
    } <= ids


def test_build_resolves_curated_links_from_frontmatter(tmp_path):
    _make_tree(tmp_path)
    result = build(tmp_path)
    edges = {(s, d): data["kind"] for s, d, data in result.store.graph.edges(data=True)}
    assert edges[("graph-content/entry", "graph-content/session/session-start")] == "curated"
    assert edges[("skills/fabric-transform", "rules/data-engineering")] == "curated"


def test_build_auto_extracts_path_mention_edges(tmp_path):
    _make_tree(tmp_path)
    result = build(tmp_path)
    edges = {(s, d): data["kind"] for s, d, data in result.store.graph.edges(data=True)}
    assert ("graph-content/entry", "rules/security") in edges
    assert edges[("graph-content/entry", "rules/security")] == "auto-path"
    assert ("graph-content/session/session-start", "skills/fabric-transform") in edges


def test_build_warns_on_orphans(tmp_path):
    _make_tree(tmp_path)
    _write(tmp_path / "templates" / "lonely.md", "# Lonely\n")
    result = build(tmp_path)
    assert any("templates/lonely" in w for w in result.warnings)


def test_build_warns_and_keeps_first_on_duplicate_id(tmp_path):
    _make_tree(tmp_path)
    _write(
        tmp_path / "memory" / "MEMORY.md",
        "---\nname: memory-dup\n---\n\n# Dup runtime memory\n",
    )
    _write(
        tmp_path / "profiles" / "shared" / "memory" / "MEMORY.md",
        "---\nname: memory-source\n---\n\n# Source memory\n",
    )
    result = build(tmp_path)
    assert any("duplicate node id" in w for w in result.warnings)
    assert result.errors == []
    node = result.store.get_node("memory/MEMORY")
    assert node.path.startswith("profiles/shared/memory/")


def test_build_errors_on_unresolved_curated_link(tmp_path):
    _make_tree(tmp_path)
    _write(
        tmp_path / "rules" / "broken.md",
        "---\nname: broken\nlinks:\n  - rules/does-not-exist\n---\n\n# Broken\n",
    )
    result = build(tmp_path)
    assert any("unresolved curated link" in err for err in result.errors)


def test_id_from_path_handles_known_locations():
    cases = {
        "memory/graph-content/entry.md": "graph-content/entry",
        "memory/graph-content/workflow/pipeline-structure.md": "graph-content/workflow/pipeline-structure",
        "memory/rules/data-engineering.md": "rules/data-engineering",
        "rules/data-engineering.md": "rules/data-engineering",
        "memory/skill-fixes/silver-do-not-trust-bronze-types.md": "skill-fixes/silver-do-not-trust-bronze-types",
        "memory/lux_energy_price/project.md": "topic/lux_energy_price/project",
        ".claude/skills/fabric-transform/SKILL.md": "skills/fabric-transform",
        "profiles/skills/fabric-transform/SKILL.md": "skills/fabric-transform",
        "templates/runbook.md": "templates/runbook",
    }
    for path, expected in cases.items():
        assert id_from_path(path) == expected, f"{path} -> {id_from_path(path)} != {expected}"


def test_parse_frontmatter_extracts_links_list():
    text = "---\nname: foo\nlinks:\n  - rules/a\n  - rules/b\n---\n\nbody\n"
    fm, body = parse_frontmatter(text)
    assert fm["name"] == "foo"
    assert fm["links"] == ["rules/a", "rules/b"]
    assert body.strip() == "body"


def test_parse_frontmatter_flattens_nested_mapping():
    text = "---\nname: foo\nmetadata:\n  type: feedback\n  date: 2026-05-24\n---\n\nbody\n"
    fm, _ = parse_frontmatter(text)
    assert fm["metadata.type"] == "feedback"
    assert fm["metadata.date"] == "2026-05-24"


def test_parse_frontmatter_handles_quoted_values():
    text = "---\nname: foo\ndescription: \"A: colon-bearing description.\"\n---\n\nbody\n"
    fm, _ = parse_frontmatter(text)
    assert fm["description"] == "A: colon-bearing description."
