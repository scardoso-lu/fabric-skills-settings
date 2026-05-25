"""Build a derived graph that mirrors the native agent → skill/rule wiring.

Each native subagent declares the skills and rules it uses in its frontmatter
(``links:`` and ``skills:``). This module reads those declarations and
produces a small, explicit graph:

- 4 capability nodes (orchestrator, developer, tester, operator)
- ``capability-route`` edges between capabilities (orchestrator is the hub)
- ``capability-covers`` edges from a capability to each declared knowledge node

No keyword/prefix matching. If an agent file does not reference a node, the
capability does not cover it. This keeps the inspection graph honest about
what each agent actually knows about.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from graph.schema import Edge, Node, parse_frontmatter
from graph.store import GraphStore

CAPABILITIES: dict[str, dict[str, object]] = {
    "capabilities/orchestrator": {
        "title": "Orchestrator",
        "description": "Scopes requests, routes to one subagent at a time, owns human handoff.",
        "agent": "orchestrator",
        "routes_to": (
            "capabilities/developer",
            "capabilities/tester",
            "capabilities/operator",
        ),
    },
    "capabilities/developer": {
        "title": "Developer",
        "description": "Implements Fabric notebooks, transforms, models, mock data, and pipelines.",
        "agent": "developer",
        "routes_to": ("capabilities/orchestrator",),
    },
    "capabilities/tester": {
        "title": "Tester",
        "description": "Validates DQ, schema drift, RI, masking, and lineage envelopes.",
        "agent": "tester",
        "routes_to": ("capabilities/orchestrator",),
    },
    "capabilities/operator": {
        "title": "Operator",
        "description": "Reviews security, secrets, access, PII, and supply-chain risk.",
        "agent": "operator",
        "routes_to": ("capabilities/orchestrator",),
    },
}


@dataclass(frozen=True)
class CapabilityBuildResult:
    store: GraphStore
    warnings: list[str]


def build_agent_capability_graph(knowledge: GraphStore, root: Path) -> CapabilityBuildResult:
    """Create a derived graph from native agent frontmatter declarations.

    Only knowledge nodes that an agent explicitly references via its
    ``links:`` or ``skills:`` frontmatter are included. Capability-to-capability
    routing comes from the CAPABILITIES table (orchestrator is the hub).
    """
    out = GraphStore()
    warnings: list[str] = []
    native_agents = _native_agents(root)

    for capability_id, spec in CAPABILITIES.items():
        agent_name = str(spec["agent"])
        agent_present = agent_name in native_agents
        if not agent_present:
            warnings.append(f"native agent file missing for {capability_id}")
        out.add_node(
            Node(
                id=capability_id,
                path="",
                title=str(spec["title"]),
                description=str(spec["description"]),
                kind="capability",
                frontmatter={"agents": [agent_name] if agent_present else [agent_name]},
                mtime=0.0,
            )
        )

    for capability_id, spec in CAPABILITIES.items():
        for target in spec["routes_to"]:
            out.add_edge(Edge(src=capability_id, dst=target, kind="capability-route"))

    for capability_id, spec in CAPABILITIES.items():
        agent_name = str(spec["agent"])
        referenced = _agent_references(root, agent_name)
        for node_id in sorted(referenced):
            if node_id.startswith("capabilities/") or node_id.startswith("agents/"):
                continue
            if node_id not in knowledge.graph and not out.has_node(node_id):
                warnings.append(
                    f"{capability_id}: reference to '{node_id}' not found in knowledge graph"
                )
                continue
            if not out.has_node(node_id):
                data = knowledge.graph.nodes[node_id]
                out.add_node(
                    Node(
                        id=node_id,
                        path=data.get("path", ""),
                        title=data.get("title", node_id),
                        description=data.get("description", ""),
                        kind=data.get("kind", "content"),
                        frontmatter=dict(data.get("frontmatter") or {}),
                        mtime=float(data.get("mtime", 0.0)),
                    )
                )
            out.add_edge(Edge(src=capability_id, dst=node_id, kind="capability-covers"))

    return CapabilityBuildResult(store=out, warnings=warnings)


def _agent_references(root: Path, agent_name: str) -> set[str]:
    """Parse a native agent file's frontmatter and return the node ids it references.

    Looks at ``links:`` (raw node ids) and ``skills:`` (skill stems). Tools like
    Read/Write/Bash are not graph nodes and are skipped. Prefers the Claude file;
    falls back to the Codex TOML.
    """
    refs: set[str] = set()
    claude_md = root / "profiles" / "claude" / "agents" / f"{agent_name}.md"
    codex_toml = root / "profiles" / "codex" / "agents" / f"{agent_name}.toml"
    installed_claude = root / ".claude" / "agents" / f"{agent_name}.md"

    source: Path | None = None
    for candidate in (claude_md, installed_claude):
        if candidate.exists():
            source = candidate
            break

    if source is not None:
        text = source.read_text(encoding="utf-8", errors="ignore")
        fm, _ = parse_frontmatter(text)
        for link in _as_list(fm.get("links")):
            refs.add(link)
        for skill in _as_list(fm.get("skills")):
            refs.add(f"skills/{skill}")
    elif codex_toml.exists():
        refs.update(_parse_codex_toml(codex_toml))

    return refs


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value:
        return [value]
    return []


def _parse_codex_toml(path: Path) -> set[str]:
    """Minimal TOML-ish reader for codex agent files.

    Reads ``skills = ["a", "b"]`` and ``links = ["a", "b"]`` (single-line arrays).
    Avoids a dependency on tomllib for older runtimes.
    """
    refs: set[str] = set()
    text = path.read_text(encoding="utf-8", errors="ignore")
    for key in ("links", "skills"):
        marker = f"{key} = ["
        idx = text.find(marker)
        if idx == -1:
            continue
        end = text.find("]", idx)
        if end == -1:
            continue
        body = text[idx + len(marker) : end]
        for item in body.split(","):
            cleaned = item.strip().strip("\"'")
            if not cleaned:
                continue
            if key == "skills":
                refs.add(f"skills/{cleaned}")
            else:
                refs.add(cleaned)
    return refs


def _native_agents(root: Path) -> set[str]:
    agents: set[str] = set()
    for path in (root / "profiles" / "codex" / "agents").glob("*.toml"):
        agents.add(path.stem)
    for path in (root / "profiles" / "claude" / "agents").glob("*.md"):
        agents.add(path.stem)
    for path in (root / ".codex" / "agents").glob("*.toml"):
        agents.add(path.stem)
    for path in (root / ".claude" / "agents").glob("*.md"):
        agents.add(path.stem)
    return agents
