"use client";

import { useState } from "react";
import { useSearch, useNode } from "@/hooks/useNodes";
import { addEdge, removeEdge } from "@/lib/api";
import { kindBadgeClass, managedBadge } from "@/lib/utils";
import { useStats } from "@/hooks/useNodes";

export default function GraphPage() {
  const { data: stats } = useStats();
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [edgeSrc, setEdgeSrc] = useState("");
  const [edgeDst, setEdgeDst] = useState("");
  const [edgeError, setEdgeError] = useState<string | null>(null);
  const [edgeSaving, setEdgeSaving] = useState(false);

  const { data: searchData, isLoading: searchLoading } = useSearch(debouncedQuery);
  const { data: nodeDetail } = useNode(selectedId);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setDebouncedQuery(query.trim());
  }

  async function handleAddEdge() {
    setEdgeError(null);
    if (!edgeSrc.trim() || !edgeDst.trim()) {
      setEdgeError("Both src and dst are required");
      return;
    }
    setEdgeSaving(true);
    try {
      await addEdge(edgeSrc.trim(), edgeDst.trim());
      setEdgeSrc("");
      setEdgeDst("");
    } catch (err: unknown) {
      setEdgeError(err instanceof Error ? err.message : "Failed to add edge");
    } finally {
      setEdgeSaving(false);
    }
  }

  async function handleRemoveEdge(src: string, dst: string) {
    setEdgeError(null);
    try {
      await removeEdge(src, dst);
    } catch (err: unknown) {
      setEdgeError(err instanceof Error ? err.message : "Failed to remove edge");
    }
  }

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Graph</h1>

      {/* Stats bar */}
      {stats && (
        <div className="stats stats-horizontal shadow bg-base-200 text-sm">
          <div className="stat py-3">
            <div className="stat-title text-xs">Nodes</div>
            <div className="stat-value text-lg">{stats.nodes}</div>
          </div>
          <div className="stat py-3">
            <div className="stat-title text-xs">Edges</div>
            <div className="stat-value text-lg">{stats.edges}</div>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="card bg-base-200 shadow">
        <div className="card-body py-4">
          <h2 className="card-title text-base">Search nodes</h2>
          <form className="flex gap-2" onSubmit={handleSearch}>
            <input
              type="text"
              className="input input-bordered input-sm flex-1"
              placeholder="Search graph nodes…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button type="submit" className="btn btn-primary btn-sm">
              Search
            </button>
          </form>

          {searchLoading && (
            <div className="flex justify-center py-4">
              <span className="loading loading-spinner loading-sm" />
            </div>
          )}

          {searchData && searchData.hits.length === 0 && (
            <p className="text-sm text-base-content/50">No results for "{searchData.query}"</p>
          )}

          {searchData && searchData.hits.length > 0 && (
            <div className="flex flex-col gap-1 mt-2">
              {searchData.hits.map((hit) => (
                <button
                  key={hit.id}
                  type="button"
                  className={`text-left rounded-lg px-3 py-2 hover:bg-base-300 transition-colors ${
                    selectedId === hit.id ? "bg-base-300 ring-1 ring-primary" : ""
                  }`}
                  onClick={() => setSelectedId(hit.id)}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">{hit.title}</span>
                    <span className="badge badge-ghost badge-xs font-mono">
                      {hit.score.toFixed(2)}
                    </span>
                  </div>
                  <div className="text-xs text-base-content/50 font-mono">{hit.id}</div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Node detail */}
      {nodeDetail && (
        <div className="card bg-base-200 shadow">
          <div className="card-body py-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h2 className="card-title text-base">{nodeDetail.title}</h2>
                <span className="font-mono text-xs text-base-content/50">{nodeDetail.id}</span>
              </div>
              <div className="flex gap-1 shrink-0">
                <span className={`badge badge-sm ${kindBadgeClass(nodeDetail.kind)}`}>
                  {nodeDetail.kind}
                </span>
                <span className={`badge badge-sm ${managedBadge(nodeDetail.managed)}`}>
                  {nodeDetail.managed ? "managed" : "bundled"}
                </span>
              </div>
            </div>

            {nodeDetail.description && (
              <p className="text-sm text-base-content/70">{nodeDetail.description}</p>
            )}

            {/* Outbound links */}
            {nodeDetail.links && nodeDetail.links.length > 0 && (
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-base-content/50 mb-1">
                  Outbound links
                </div>
                <div className="flex flex-wrap gap-1">
                  {nodeDetail.links.map((link) => (
                    <div key={link} className="flex items-center gap-0.5">
                      <button
                        type="button"
                        className="badge badge-outline badge-sm font-mono hover:badge-primary"
                        onClick={() => setSelectedId(link)}
                      >
                        {link}
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost btn-xs text-error px-1"
                        title="Remove curated edge"
                        onClick={() => handleRemoveEdge(nodeDetail.id, link)}
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Inbound links */}
            {nodeDetail.inbound_links && nodeDetail.inbound_links.length > 0 && (
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-base-content/50 mb-1">
                  Inbound links
                </div>
                <div className="flex flex-wrap gap-1">
                  {nodeDetail.inbound_links.map((link) => (
                    <button
                      key={link}
                      type="button"
                      className="badge badge-outline badge-sm font-mono hover:badge-secondary"
                      onClick={() => setSelectedId(link)}
                    >
                      {link}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Edge management */}
      <div className="card bg-base-200 shadow">
        <div className="card-body py-4">
          <h2 className="card-title text-base">Add edge</h2>
          {edgeError && (
            <div role="alert" className="alert alert-error text-sm py-2">
              <span>{edgeError}</span>
            </div>
          )}
          <div className="flex gap-2 items-end flex-wrap">
            <label className="form-control flex-1 min-w-40">
              <div className="label py-0"><span className="label-text text-xs">Source node ID</span></div>
              <input
                type="text"
                className="input input-bordered input-sm font-mono"
                placeholder="skills/git-commit"
                value={edgeSrc}
                onChange={(e) => setEdgeSrc(e.target.value)}
              />
            </label>
            <span className="pb-1">→</span>
            <label className="form-control flex-1 min-w-40">
              <div className="label py-0"><span className="label-text text-xs">Destination node ID</span></div>
              <input
                type="text"
                className="input input-bordered input-sm font-mono"
                placeholder="rules/security"
                value={edgeDst}
                onChange={(e) => setEdgeDst(e.target.value)}
              />
            </label>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleAddEdge}
              disabled={edgeSaving}
            >
              {edgeSaving ? <span className="loading loading-spinner loading-xs" /> : null}
              Add
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
