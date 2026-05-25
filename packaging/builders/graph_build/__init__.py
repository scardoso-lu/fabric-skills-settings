"""Source-package build-time modules for the knowledge graph.

These modules are used by `bin/build-graph.py` and `bin/build-agent-capability-graph.py`
to build the graph artifact (graph.json, BM25 index, SVGs). They are NOT installed
into target repositories — only the runtime modules under `tool/graph/` are.

Runtime dependencies (Node, Edge, GraphStore, search) are imported from `graph.*`
(i.e. `tool/graph/`) via sys.path set up by the build scripts.
"""
