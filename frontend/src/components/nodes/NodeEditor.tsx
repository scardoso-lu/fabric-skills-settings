"use client";

import { useState } from "react";
import { NodeBadge } from "@/components/ui/NodeBadge";
import type { GraphNode } from "@/lib/types";

interface SavePayload {
  body: string;
  frontmatter: Record<string, unknown>;
}

interface NodeEditorProps {
  node: GraphNode;
  onSave: (payload: SavePayload) => void;
  onDelete: () => void;
  saving?: boolean;
  deleting?: boolean;
}

export function NodeEditor({
  node,
  onSave,
  onDelete,
  saving = false,
  deleting = false,
}: NodeEditorProps) {
  const fm = (node.frontmatter ?? {}) as Record<string, string>;
  const [name, setName] = useState<string>(fm.name ?? node.title ?? "");
  const [description, setDescription] = useState<string>(
    fm.description ?? node.description ?? "",
  );
  const [allowedTools, setAllowedTools] = useState<string>(
    (fm["allowed-tools"] as string) ?? "",
  );
  const [body, setBody] = useState<string>(node.body ?? "");
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  function handleSave() {
    const frontmatter: Record<string, unknown> = { name, description };
    if (allowedTools.trim()) frontmatter["allowed-tools"] = allowedTools.trim();
    onSave({ body, frontmatter });
  }

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <NodeBadge kind={node.kind} managed={node.managed} />
        <span className="text-xs text-base-content/50 font-mono truncate max-w-xs">
          {node.path}
        </span>
      </div>

      {/* Frontmatter fields */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label className="form-control w-full">
          <div className="label">
            <span className="label-text">Name</span>
          </div>
          <input
            className="input input-bordered input-sm w-full"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="skill-name"
          />
        </label>

        {node.kind === "skill" && (
          <label className="form-control w-full">
            <div className="label">
              <span className="label-text">Allowed Tools</span>
            </div>
            <input
              className="input input-bordered input-sm w-full"
              value={allowedTools}
              onChange={(e) => setAllowedTools(e.target.value)}
              placeholder="Bash, Read, Edit"
            />
          </label>
        )}

        <label className="form-control md:col-span-2 w-full">
          <div className="label">
            <span className="label-text">Description</span>
          </div>
          <input
            className="input input-bordered input-sm w-full"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Short one-line description"
          />
        </label>
      </div>

      {/* Body editor */}
      <label className="form-control w-full flex-1 min-h-0">
        <div className="label">
          <span className="label-text">Body (Markdown)</span>
        </div>
        <textarea
          aria-label="body"
          className="textarea textarea-bordered font-mono text-sm w-full flex-1 resize-none h-full min-h-[300px]"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          spellCheck={false}
        />
      </label>

      {/* Actions */}
      <div className="flex justify-between items-center gap-2">
        <button
          type="button"
          className="btn btn-error btn-outline btn-sm"
          onClick={() => setShowDeleteModal(true)}
          disabled={deleting || saving}
        >
          {deleting ? (
            <span className="loading loading-spinner loading-xs" />
          ) : null}
          Delete
        </button>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={handleSave}
          disabled={saving || deleting}
        >
          {saving ? (
            <span className="loading loading-spinner loading-xs" />
          ) : null}
          Save
        </button>
      </div>

      {/* Delete confirmation modal */}
      {showDeleteModal && (
        <dialog className="modal modal-open">
          <div className="modal-box">
            <h3 className="font-bold text-lg">Delete node?</h3>
            <p className="py-4 text-sm">
              This will permanently remove{" "}
              <span className="font-mono font-bold">{node.id}</span> from the
              graph. This action cannot be undone.
            </p>
            <div className="modal-action">
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setShowDeleteModal(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-error btn-sm"
                onClick={() => {
                  setShowDeleteModal(false);
                  onDelete();
                }}
              >
                Confirm
              </button>
            </div>
          </div>
          <div
            className="modal-backdrop"
            onClick={() => setShowDeleteModal(false)}
          />
        </dialog>
      )}
    </div>
  );
}
