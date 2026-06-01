"use client";

import { useState } from "react";
import {
  useNodes,
  useNode,
  saveNode,
  removeNode,
  invalidateNodes,
} from "@/hooks/useNodes";
import { NodeList } from "@/components/nodes/NodeList";
import { NodeEditor } from "@/components/nodes/NodeEditor";
import { logAudit } from "@/lib/audit";
import type { GraphNode } from "@/lib/types";

export default function MemoryPage() {
  const { data: nodesData, isLoading } = useNodes("memory");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creatingNew, setCreatingNew] = useState(false);
  const [newName, setNewName] = useState("");

  const { data: selectedNode, isLoading: nodeLoading } = useNode(selectedId);

  const memories = nodesData?.nodes ?? [];

  const newNodeAsGraphNode: GraphNode | null = creatingNew
    ? {
        id: newName ? `memory/${newName}` : "(new)",
        title: newName || "(new)",
        description: "",
        kind: "memory",
        path: "",
        managed: true,
        body: "",
        frontmatter: { kind: "memory" },
        links: [],
        inbound_links: [],
      }
    : null;

  const editorNode = creatingNew ? newNodeAsGraphNode : selectedNode ?? null;

  async function handleSave(payload: {
    body: string;
    frontmatter: Record<string, unknown>;
  }) {
    setError(null);
    setSaving(true);
    try {
      if (creatingNew) {
        const name = newName.trim();
        if (!name) {
          setError("Name is required");
          return;
        }
        const result = await saveNode(null, {
          newId: `memory/${name}`,
          body: payload.body,
          frontmatter: { ...payload.frontmatter, kind: "memory" },
          kind: "memory",
        });
        logAudit({ ts: Date.now(), action: "create", nodeId: result.id, nodeKind: "memory" });
        setCreatingNew(false);
        setNewName("");
        setSelectedId(result.id);
      } else if (selectedId) {
        await saveNode(selectedId, payload);
        await invalidateNodes(selectedId);
        logAudit({ ts: Date.now(), action: "update", nodeId: selectedId, nodeKind: "memory" });
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
      logAudit({ ts: Date.now(), action: "delete", nodeId: selectedId, nodeKind: "memory" });
      setSelectedId(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="flex gap-4 h-[calc(100vh-6.5rem)]">
      {/* Left panel */}
      <div className="w-64 shrink-0 flex flex-col gap-2 bg-white rounded-xl border border-slate-200 shadow-sm p-3 overflow-hidden">
        <div className="flex items-center justify-between gap-1">
          <h2 className="font-semibold text-sm text-slate-700">Memory</h2>
          <button
            type="button"
            className="btn btn-primary btn-xs"
            onClick={() => {
              setCreatingNew(true);
              setSelectedId(null);
              setNewName("");
            }}
          >
            + New
          </button>
        </div>
        <input
          type="text"
          className="input input-bordered input-xs w-full"
          placeholder="Filter memories…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="overflow-y-auto flex-1">
          {isLoading ? (
            <div className="flex justify-center py-4">
              <span className="loading loading-spinner loading-sm text-primary" />
            </div>
          ) : memories.length === 0 && !isLoading ? (
            <p className="text-xs text-slate-400 px-2 py-3 text-center">No memories yet</p>
          ) : (
            <NodeList
              nodes={memories}
              selectedId={selectedId ?? undefined}
              onSelect={(n) => {
                setSelectedId(n.id);
                setCreatingNew(false);
              }}
              searchQuery={search}
            />
          )}
        </div>
      </div>

      {/* Right panel */}
      <div className="flex-1 bg-white rounded-xl border border-slate-200 shadow-sm p-5 overflow-auto flex flex-col gap-3">
        {error && (
          <div role="alert" className="alert alert-error text-sm py-2">
            <span>{error}</span>
            <button
              type="button"
              className="btn btn-ghost btn-xs"
              onClick={() => setError(null)}
            >
              ✕
            </button>
          </div>
        )}

        {creatingNew && (
          <div className="flex gap-2 items-end flex-wrap bg-slate-50 rounded-lg border border-slate-200 p-3">
            <label className="form-control flex-1 min-w-48">
              <div className="label py-0">
                <span className="label-text text-xs font-medium text-slate-600">Name</span>
                <span className="label-text-alt text-xs text-slate-400">memory/…</span>
              </div>
              <input
                type="text"
                className="input input-bordered input-sm w-full font-mono"
                placeholder="e.g. project-context"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                autoFocus
              />
            </label>
          </div>
        )}

        {nodeLoading && !creatingNew ? (
          <div className="flex justify-center py-12">
            <span className="loading loading-spinner loading-lg text-primary" />
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
          <div className="flex flex-col items-center justify-center flex-1 gap-3">
            <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center">
              <svg width="22" height="22" fill="none" viewBox="0 0 24 24" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2v-4M9 21H5a2 2 0 01-2-2v-4m0 0h18" />
              </svg>
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-slate-600">No memory selected</p>
              <p className="text-xs text-slate-400 mt-0.5">
                Choose a memory from the list or create a new one
              </p>
            </div>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => {
                setCreatingNew(true);
                setNewName("");
              }}
            >
              + New memory
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
