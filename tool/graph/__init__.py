"""Knowledge graph over the Fabric agent profile vault.

Modules:
  schema   Node, Edge, frontmatter parser, path -> id mapping.
  store    networkx-backed graph + atomic save/load.
  lock     cross-platform exclusive file lock.
  extract  auto-edge regex extraction from prose.
  search   BM25 index + 1-hop edge-aware re-rank.
  builder  discover + parse + edges + validate pipeline.
"""
