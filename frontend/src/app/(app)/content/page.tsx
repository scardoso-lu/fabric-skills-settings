"use client";

import { useState } from "react";
import { useNodes, useNode, saveNode, removeNode, invalidateNodes } from "@/hooks/useNodes";
import { NodeList } from "@/components/nodes/NodeList";
import { NodeEditor } from "@/components/nodes/NodeEditor";
import type { GraphNode, NodeKind } from "@/lib/types";

const CONTENT_KINDS: NodeKind[] = ["content", "rule", "memory", "skill-fix"];

export default function ContentPage() {
  const [kindFilter, setKindFilter] = useState<NodeKind | "">("");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creatingNew, setCreatingNew] = useState(false);
  const [newNodeId, setNewNodeId] = useState("");
  const [newKind, setNewKind] = useState<NodeKind>("content");
  const [newBody, setNewBody] = useState("");

  const { data: nodesData, isLoading } = useNodes(kindFilter || undefined);
  const { data: selectedNode, isLoading: nodeLoading } = useNode(selectedId);

  const nodes = (nodesData?.nodes ?? []).filter(
    (n) => !["skill", "entry"].includes(n.kind),
  );

  async function handleSave(payload: { body: string; frontmatter: Record<string, unknown> }) {
    setError(null);
    setSaving(true);
    try {
      if (creatingNew) {
        const id = newNodeId.trim();
        if (!id) { setError("Node ID is required"); return; }
        const result = await saveNode(null, {
          newId: id,
          body: payload.body,
          frontmatter: { ...payload.frontmatter, kind: newKind },
          kind: newKind,
        });
        setCreatingNew(false);
        setSelectedId(result.id);
      } else if (selectedId) {
        await saveNode(selectedId, payload);
        await invalidateNodes(selectedId);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!selectedId) return;
    setDeleting(true);
    try {
      await removeNode(selectedId);
      setSelectedId(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  }

  const newNodeAsGraphNode: GraphNode | null = creatingNew
    ? {
        id: newNodeId || "(new)",
        title: newNodeId || "(new)",
        description: "",
        kind: newKind,
        path: "",
        managed: true,
        body: newBody,
        frontmatter: { kind: newKind },
        links: [],
        inbound_links: [],
      }
    : null;

  const editorNode = creatingNew ? newNodeAsGraphNode : selectedNode ?? null;

  return (
    <div className="flex gap-4 h-[calc(100vh-3rem)]">
      {/* Left panel */}
      <div className="w-64 shrink-0 flex flex-col gap-2 bg-base-200 rounded-xl p-3 overflow-hidden">
        <div className="flex items-center justify-between gap-1">
          <h2 className="font-semibold text-sm">Content</h2>
          <button
            type="button"
            className="btn btn-primary btn-xs"
            onClick={() => { setCreatingNew(true); setSelectedId(null); setNewNodeId(""); setNewBody(""); }}
          >
            + New
          </button>
        </div>

        <select
          className="select select-bordered select-xs w-full"
          value={kindFilter}
          onChange={(e) => setKindFilter(e.target.value as NodeKind | "")}
        >
          <option value="">All kinds</option>
          {CONTENT_KINDS.map((k) => (
            <option key={k} value={k}>{k}</option>
          ))}
        </select>

        <input
          type="text"
          className="input input-bordered input-xs w-full"
          placeholder="Filter…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />

        <div className="overflow-y-auto flex-1">
          {isLoading ? (
            <div className="flex justify-center py-4">
              <span className="loading loading-spinner loading-sm" />
            </div>
          ) : (
            <NodeList
              nodes={nodes}
              selectedId={selectedId ?? undefined}
              onSelect={(n) => { setSelectedId(n.id); setCreatingNew(false); }}
              searchQuery={search}
            />
          )}
        </div>
      </div>

      {/* Right panel */}
      <div className="flex-1 bg-base-200 rounded-xl p-4 overflow-auto flex flex-col gap-3">
        {error && (
          <div role="alert" className="alert alert-error text-sm py-2">
            <span>{error}</span>
            <button type="button" className="btn btn-ghost btn-xs" onClick={() => setError(null)}>✕</button>
          </div>
        )}

        {creatingNew && (
          <div className="flex gap-2 items-end flex-wrap bg-base-300 rounded-lg p-3">
            <label className="form-control">
              <div className="label py-0"><span className="label-text text-xs">Kind</span></div>
              <select
                className="select select-bordered select-sm"
                value={newKind}
                onChange={(e) => setNewKind(e.target.value as NodeKind)}
              >
                {CONTENT_KINDS.map((k) => (
                  <option key={k} value={k}>{k}</option>
                ))}
              </select>
            </label>
            <label className="form-control flex-1 min-w-48">
              <div className="label py-0"><span className="label-text text-xs">Node ID</span></div>
              <input
                type="text"
                className="input input-bordered input-sm w-full font-mono"
                placeholder="rules/my-rule or graph-content/my-page"
                value={newNodeId}
                onChange={(e) => setNewNodeId(e.target.value)}
              />
            </label>
          </div>
        )}

        {nodeLoading && !creatingNew ? (
          <div className="flex justify-center py-12">
            <span className="loading loading-spinner loading-lg" />
          </div>
        ) : editorNode ? (
          <NodeEditor
            node={editorNode}
            onSave={handleSave}
            onDelete={handleDelete}
            saving={saving}
            deleting={deleting}
          />
        ) : (
          <div className="flex flex-col items-center justify-center flex-1 text-base-content/40 gap-3">
            <span className="text-4xl">📄</span>
            <p className="text-sm">Select a node or create a new one</p>
          </div>
        )}
      </div>
    </div>
  );
}
