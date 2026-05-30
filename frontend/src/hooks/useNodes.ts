"use client";

import useSWR, { mutate as globalMutate } from "swr";
import {
  fetchNodes,
  fetchNode,
  fetchStats,
  fetchTemplates,
  createNode,
  updateNode,
  deleteNode,
  fetchTemplate,
  searchNodes,
} from "@/lib/api";
import type { GraphNode, NodeKind } from "@/lib/types";

const NODES_KEY = (kind?: string) => `/api/v1/nodes${kind ? `?kind=${kind}` : ""}`;
const NODE_KEY = (id: string) => `/api/v1/nodes/${id}`;
const STATS_KEY = "/api/v1/stats";
const TEMPLATES_KEY = "/api/v1/templates";

export function useStats() {
  return useSWR(STATS_KEY, fetchStats, { refreshInterval: 30_000 });
}

export function useNodes(kind?: string) {
  return useSWR(NODES_KEY(kind), () => fetchNodes(kind), {
    revalidateOnFocus: false,
  });
}

export function useNode(id: string | null) {
  return useSWR(id ? NODE_KEY(id) : null, () => fetchNode(id!), {
    revalidateOnFocus: false,
  });
}

export function useTemplates() {
  return useSWR(TEMPLATES_KEY, fetchTemplates, { revalidateOnFocus: false });
}

export function useSearch(query: string, k = 10) {
  return useSWR(
    query.trim() ? [`/api/v1/search`, query] : null,
    () => searchNodes(query, k),
    { revalidateOnFocus: false },
  );
}

export async function invalidateNodes(id?: string) {
  await globalMutate(STATS_KEY);
  await globalMutate((key) => typeof key === "string" && key.startsWith("/api/v1/nodes"), undefined, { revalidate: true });
  if (id) await globalMutate(NODE_KEY(id));
}

export async function saveNode(
  id: string | null,
  payload: {
    newId?: string;
    body: string;
    frontmatter?: Record<string, unknown>;
    kind?: NodeKind;
  },
): Promise<GraphNode> {
  if (id) {
    const result = await updateNode(id, {
      body: payload.body,
      frontmatter: payload.frontmatter,
    });
    await invalidateNodes(id);
    return { id: result.id } as GraphNode;
  } else {
    if (!payload.newId) throw new Error("id required for create");
    const result = await createNode({
      id: payload.newId,
      body: payload.body,
      frontmatter: payload.frontmatter,
    });
    await invalidateNodes(result.id);
    return { id: result.id } as GraphNode;
  }
}

export async function removeNode(id: string): Promise<void> {
  await deleteNode(id);
  await invalidateNodes();
}

export { fetchTemplate };
