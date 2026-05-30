/**
 * API client — all requests go through the same-origin BFF proxy
 * (/api/proxy/**) so the server can attach the httpOnly JWT cookie as
 * an Authorization header before forwarding to the FastMCP backend.
 * The JWT never touches browser JS.
 */
import { clearExpiresAt } from "./auth";
import type {
  GraphNode,
  GraphStats,
  SearchHit,
  Template,
  TemplateDetail,
  WriteResult,
} from "./types";

// All API traffic goes to the same-origin proxy — no CORS, no token in JS.
const PROXY_BASE = "/api/proxy";

class ApiResponseError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiResponseError";
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  const res = await fetch(`${PROXY_BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    clearExpiresAt();
    window.location.href = "/login";
    throw new ApiResponseError(401, "Session expired");
  }

  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = body.error ?? message;
    } catch {
      // non-JSON error body — use statusText
    }
    throw new ApiResponseError(res.status, message);
  }

  return res.json() as Promise<T>;
}

// ── auth ──────────────────────────────────────────────────────────────────────
// Login goes to the Next.js API route (not the proxy) — it sets the httpOnly cookie.

export async function login(
  apiKey: string,
): Promise<{ expires_at: string; token_type: string }> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiResponseError(res.status, body.error ?? "Login failed");
  }
  return res.json();
}

export async function refreshToken(): Promise<void> {
  const res = await fetch("/api/auth/refresh", { method: "POST" });
  if (!res.ok) {
    clearExpiresAt();
    window.location.href = "/login";
  } else {
    const { expires_at } = await res.json();
    const { setExpiresAt } = await import("./auth");
    setExpiresAt(expires_at);
  }
}

// ── graph ─────────────────────────────────────────────────────────────────────

export async function fetchStats(): Promise<GraphStats> {
  return request<GraphStats>("/stats");
}

export async function fetchNodes(kind?: string): Promise<{ nodes: GraphNode[] }> {
  const qs = kind ? `?kind=${encodeURIComponent(kind)}` : "";
  return request<{ nodes: GraphNode[] }>(`/nodes${qs}`);
}

export async function fetchNode(id: string): Promise<GraphNode> {
  return request<GraphNode>(`/nodes/${encodeNodeId(id)}`);
}

export async function createNode(payload: {
  id: string;
  body: string;
  frontmatter?: Record<string, unknown>;
  links?: string[];
}): Promise<WriteResult> {
  return request<WriteResult>("/nodes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateNode(
  id: string,
  payload: { body?: string; frontmatter?: Record<string, unknown> },
): Promise<WriteResult> {
  return request<WriteResult>(`/nodes/${encodeNodeId(id)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function deleteNode(
  id: string,
  allowOrphans = false,
): Promise<WriteResult> {
  return request<WriteResult>(
    `/nodes/${encodeNodeId(id)}?allow_orphans=${allowOrphans}`,
    { method: "DELETE" },
  );
}

export async function searchNodes(
  q: string,
  k = 10,
): Promise<{ query: string; hits: SearchHit[] }> {
  return request<{ query: string; hits: SearchHit[] }>(
    `/search?q=${encodeURIComponent(q)}&k=${k}`,
  );
}

export async function addEdge(src: string, dst: string): Promise<WriteResult> {
  return request<WriteResult>("/edges", {
    method: "POST",
    body: JSON.stringify({ src, dst }),
  });
}

export async function removeEdge(src: string, dst: string): Promise<WriteResult> {
  return request<WriteResult>("/edges", {
    method: "DELETE",
    body: JSON.stringify({ src, dst }),
  });
}

// ── templates ─────────────────────────────────────────────────────────────────

export async function fetchTemplates(): Promise<{ templates: Template[] }> {
  return request<{ templates: Template[] }>("/templates");
}

export async function fetchTemplate(name: string): Promise<TemplateDetail> {
  return request<TemplateDetail>(`/templates/${encodeURIComponent(name)}`);
}

// ── helpers ───────────────────────────────────────────────────────────────────

function encodeNodeId(id: string): string {
  return id.split("/").map(encodeURIComponent).join("/");
}

export { ApiResponseError };
