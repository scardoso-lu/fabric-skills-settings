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
        root / "content" / "graph-content" / "entry.md",
        "---\nname: entry\ndescription: Setup gate\nlinks:\n  - graph-content/session/session-start\n---\n\n# Entry\nSee content/rules/security.md and skills/fabric-transform.\n",
    )
    _write(
        root / "content" / "graph-content" / "session" / "session-start.md",
        "---\nname: session-start\ndescription: Read order\n---\n\n# Session start\nWorkflows in profiles/skills/fabric-transform/SKILL.md.\n",
    )
    _write(
        root / "profiles" / "skills" / "fabric-transform" / "SKILL.md",
        "---\nname: fabric-transform\ndescription: Silver/Gold transform skill\nlinks:\n  - rules/data-engineering\n---\n\n# fabric-transform\nMERGE pattern with idempotent upsert.\n",
    )
    _write(
        root / "content" / "rules" / "data-engineering.md",
        "---\nname: data-engineering\ndescription: Pipeline rules\n---\n\n# Data engineering rules\nIdempotency required.\n",
    )
    _write(
        root / "content" / "rules" / "security.md",
        "---\nname: security\ndescription: Secrets handling rules\n---\n\n# Security\nNever commit credentials.\n",
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


def test_build_does_not_index_native_agent_files(tmp_path):
    _make_tree(tmp_path)
    _write(
        tmp_path / ".claude" / "agents" / "developer.md",
        "---\nname: developer\n---\n\n# Developer\nUse profiles/skills/fabric-transform/SKILL.md.\n",
    )
    _write(
        tmp_path / ".codex" / "agents" / "developer.toml",
        'name = "developer"\n'
        'description = "Implements Microsoft Fabric work."\n'
        'developer_instructions = """Use profiles/skills/fabric-transform/SKILL.md."""\n',
    )
    result = build(tmp_path)
    assert result.errors == []
    assert "agents/developer" not in set(result.store.graph.nodes)


def test_build_warns_on_orphans(tmp_path):
    _make_tree(tmp_path)
    _write(tmp_path / "memory" / "skill-fixes" / "lonely-issue.md", "---\nname: lonely-issue\n---\n\n# Lonely\n")
    result = build(tmp_path)
    assert any("skill-fixes/lonely-issue" in w for w in result.warnings)


def test_build_warns_and_keeps_first_on_duplicate_id(tmp_path):
    _make_tree(tmp_path)
    _write(
        tmp_path / "memory" / "graph-content" / "entry.md",
        "---\nname: entry\ndescription: Runtime install of entry\n---\n\n# Entry dup\n",
    )
    result = build(tmp_path)
    assert any("duplicate node id" in w for w in result.warnings)
    assert result.errors == []
    node = result.store.get_node("graph-content/entry")
    assert node.path.startswith("content/graph-content/")


def test_build_errors_on_unresolved_curated_link(tmp_path):
    _make_tree(tmp_path)
    _write(
        tmp_path / "content" / "rules" / "broken.md",
        "---\nname: broken\nlinks:\n  - rules/does-not-exist\n---\n\n# Broken\n",
    )
    result = build(tmp_path)
    assert any("unresolved curated link" in err for err in result.errors)


def test_id_from_path_handles_known_locations():
    cases = {
        "memory/graph-content/entry.md": "graph-content/entry",
        "memory/graph-content/workflow/pipeline-structure.md": "graph-content/workflow/pipeline-structure",
        "memory/rules/data-engineering.md": "rules/data-engineering",
        "content/rules/data-engineering.md": "rules/data-engineering",
        "content/graph-content/entry.md": "graph-content/entry",
        "memory/skill-fixes/silver-do-not-trust-bronze-types.md": "skill-fixes/silver-do-not-trust-bronze-types",
        ".claude/skills/fabric-transform/SKILL.md": "skills/fabric-transform",
        "profiles/skills/fabric-transform/SKILL.md": "skills/fabric-transform",
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
