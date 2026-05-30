"use client";

import { kindBadgeClass, managedBadge } from "@/lib/utils";
import type { GraphNode } from "@/lib/types";

interface NodeListProps {
  nodes: GraphNode[];
  selectedId?: string;
  onSelect: (node: GraphNode) => void;
  searchQuery?: string;
}

export function NodeList({
  nodes,
  selectedId,
  onSelect,
  searchQuery = "",
}: NodeListProps) {
  const filtered = searchQuery
    ? nodes.filter(
        (n) =>
          n.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          n.id.toLowerCase().includes(searchQuery.toLowerCase()),
      )
    : nodes;

  if (filtered.length === 0) {
    return (
      <div className="text-base-content/50 text-sm p-4 text-center">
        No nodes found
      </div>
    );
  }

  return (
    <ul className="menu menu-sm gap-0.5 p-0 w-full">
      {filtered.map((node) => (
        <li key={node.id}>
          <button
            type="button"
            className={`flex flex-col items-start gap-0.5 text-left w-full rounded-lg px-3 py-2 ${
              selectedId === node.id ? "active" : ""
            }`}
            onClick={() => onSelect(node)}
          >
            <span className="font-medium text-sm truncate w-full">
              {node.title}
            </span>
            {node.description && (
              <span className="text-xs text-base-content/60 truncate w-full">
                {node.description}
              </span>
            )}
            <span className="flex gap-1 mt-0.5">
              <span
                className={`badge badge-xs ${kindBadgeClass(node.kind)}`}
              >
                {node.kind}
              </span>
              <span className={`badge badge-xs ${managedBadge(node.managed)}`}>
                {node.managed ? "managed" : "bundled"}
              </span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
