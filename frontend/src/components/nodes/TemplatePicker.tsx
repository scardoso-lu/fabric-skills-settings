"use client";

import { useState } from "react";
import type { Template } from "@/lib/types";

interface TemplatePickerProps {
  templates: Template[];
  onSelect: (name: string) => void;
  onClose: () => void;
}

export function TemplatePicker({
  templates,
  onSelect,
  onClose,
}: TemplatePickerProps) {
  const [selected, setSelected] = useState<string>("");
  const [search, setSearch] = useState("");

  const filtered = templates.filter(
    (t) =>
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.description.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <dialog className="modal modal-open">
      <div className="modal-box max-w-lg">
        <h3 className="font-bold text-lg mb-3">Pick a template</h3>

        <input
          type="text"
          className="input input-bordered input-sm w-full mb-3"
          placeholder="Search templates…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          autoFocus
        />

        <div className="flex flex-col gap-1 max-h-72 overflow-y-auto">
          <label className="flex items-start gap-2 p-2 rounded-lg cursor-pointer hover:bg-base-200">
            <input
              type="radio"
              name="template"
              className="radio radio-sm mt-0.5"
              checked={selected === ""}
              onChange={() => setSelected("")}
            />
            <div>
              <div className="font-medium text-sm">Start blank</div>
              <div className="text-xs text-base-content/60">Empty skill body</div>
            </div>
          </label>
          {filtered.map((t) => (
            <label
              key={t.name}
              className="flex items-start gap-2 p-2 rounded-lg cursor-pointer hover:bg-base-200"
            >
              <input
                type="radio"
                name="template"
                className="radio radio-sm mt-0.5"
                checked={selected === t.name}
                onChange={() => setSelected(t.name)}
              />
              <div>
                <div className="font-medium text-sm font-mono">{t.name}</div>
                {t.description && (
                  <div className="text-xs text-base-content/60 line-clamp-2">
                    {t.description}
                  </div>
                )}
              </div>
            </label>
          ))}
        </div>

        <div className="modal-action">
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => onSelect(selected)}
          >
            Use template
          </button>
        </div>
      </div>
      <div className="modal-backdrop" onClick={onClose} />
    </dialog>
  );
}
