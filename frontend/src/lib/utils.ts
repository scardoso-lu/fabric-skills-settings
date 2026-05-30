import type { NodeKind } from "./types";

export const KIND_BADGE: Record<NodeKind | string, string> = {
  skill: "badge-primary",
  rule: "badge-warning",
  content: "badge-info",
  memory: "badge-secondary",
  "skill-fix": "badge-accent",
  entry: "badge-error",
  capability: "badge-ghost",
  profile: "badge-ghost",
};

export function kindBadgeClass(kind: string): string {
  return KIND_BADGE[kind] ?? "badge-ghost";
}

export function managedBadge(managed: boolean): string {
  return managed ? "badge-success" : "badge-warning";
}

export function managedLabel(managed: boolean): string {
  return managed ? "managed" : "bundled";
}
