"use client";

import { useState } from "react";
import { useNodes, useNode, useTemplates, saveNode, removeNode, fetchTemplate, invalidateNodes } from "@/hooks/useNodes";
import { NodeList } from "@/components/nodes/NodeList";
import { NodeEditor } from "@/components/nodes/NodeEditor";
import { TemplatePicker } from "@/components/nodes/TemplatePicker";
import type { GraphNode } from "@/lib/types";

export default function SkillsPage() {
  const { data: nodesData, isLoading } = useNodes("skill");
  const { data: templatesData } = useTemplates();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showTemplatePicker, setShowTemplatePicker] = useState(false);
  const [creatingNew, setCreatingNew] = useState(false);
  const [newNode, setNewNode] = useState<GraphNode | null>(null);

  const { data: selectedNode, isLoading: nodeLoading } = useNode(selectedId);

  const skills = nodesData?.nodes ?? [];
  const templates = templatesData?.templates ?? [];

  async function handleTemplatePick(templateName: string) {
    setShowTemplatePicker(false);
    let body = "";
    let fm: Record<string, unknown> = {};
    if (templateName) {
      try {
        const tpl = await fetchTemplate(templateName);
        body = tpl.body;
        fm = tpl.frontmatter;
      } catch {
        body = "";
      }
    }
    setNewNode({
      id: "",
      title: "",
      description: "",
      kind: "skill",
      path: "",
      managed: true,
      body,
      frontmatter: fm,
      links: [],
      inbound_links: [],
    });
    setCreatingNew(true);
    setSelectedId(null);
  }

  async function handleSave(payload: { body: string; frontmatter: Record<string, unknown> }) {
    setError(null);
    setSaving(true);
    try {
      if (creatingNew && newNode !== null) {
        const name = String(payload.frontmatter.name ?? "").trim();
        if (!name) { setError("Name is required"); return; }
        const result = await saveNode(null, {
          newId: `skills/${name}`,
          body: payload.body,
          frontmatter: payload.frontmatter,
        });
        setCreatingNew(false);
        setNewNode(null);
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

  const editorNode =
    creatingNew && newNode ? newNode : selectedNode ?? null;

  return (
    <div className="flex gap-4 h-[calc(100vh-3rem)]">
      {/* Left panel */}
      <div className="w-64 shrink-0 flex flex-col gap-2 bg-base-200 rounded-xl p-3 overflow-hidden">
        <div className="flex items-center justify-between gap-1">
          <h2 className="font-semibold text-sm">Skills</h2>
          <button
            type="button"
            className="btn btn-primary btn-xs"
            onClick={() => setShowTemplatePicker(true)}
          >
            + New
          </button>
        </div>
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
              nodes={skills}
              selectedId={selectedId ?? undefined}
              onSelect={(n) => { setSelectedId(n.id); setCreatingNew(false); }}
              searchQuery={search}
            />
          )}
        </div>
      </div>

      {/* Right panel */}
      <div className="flex-1 bg-base-200 rounded-xl p-4 overflow-auto flex flex-col">
        {error && (
          <div role="alert" className="alert alert-error text-sm py-2 mb-3">
            <span>{error}</span>
            <button type="button" className="btn btn-ghost btn-xs" onClick={() => setError(null)}>✕</button>
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
            <span className="text-4xl">🎯</span>
            <p className="text-sm">Select a skill or create a new one</p>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => setShowTemplatePicker(true)}
            >
              + New skill
            </button>
          </div>
        )}
      </div>

      {showTemplatePicker && (
        <TemplatePicker
          templates={templates}
          onSelect={handleTemplatePick}
          onClose={() => setShowTemplatePicker(false)}
        />
      )}
    </div>
  );
}
