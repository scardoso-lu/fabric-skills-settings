"""Auto-edge extraction tests."""
from __future__ import annotations

from graph.extract import extract_paths, strip_code


def test_extracts_md_path_mentions():
    body = "See memory/skill-fixes/foo.md for details, and rules/security.md too."
    assert extract_paths(body) == [
        "memory/skill-fixes/foo.md",
        "rules/security.md",
    ]


def test_dedupes_in_first_occurrence_order():
    body = "rules/a.md then rules/b.md then rules/a.md again"
    assert extract_paths(body) == ["rules/a.md", "rules/b.md"]


def test_ignores_paths_inside_fenced_code():
    body = """
Before fence.
```python
# rules/inside-code.md should not match
```
After fence: rules/outside.md
"""
    assert extract_paths(body) == ["rules/outside.md"]


def test_ignores_paths_inside_inline_code():
    body = "Run `tool/notebook/build.py` and read profiles/skills/foo/SKILL.md"
    paths = extract_paths(body)
    assert "tool/notebook/build.py" not in paths
    assert "profiles/skills/foo/SKILL.md" in paths


def test_strip_code_keeps_surrounding_prose():
    body = "before\n```\nignored\n```\nafter"
    assert "before" in strip_code(body)
    assert "after" in strip_code(body)
    assert "ignored" not in strip_code(body)


def test_skips_relative_traversal():
    body = "Look at ../escape.md please."
    assert extract_paths(body) == []
