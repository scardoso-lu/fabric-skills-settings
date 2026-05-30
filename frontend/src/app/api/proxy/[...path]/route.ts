/**
 * BFF proxy — forwards /api/proxy/** → backend /api/v1/**.
 *
 * All API calls from the browser go to this same-origin proxy. The proxy
 * reads the httpOnly `fab_token` cookie (inaccessible to browser JS) and
 * adds the Authorization header before forwarding to the FastMCP server.
 *
 * Security: token never touches browser JS; httpOnly + SameSite=Strict
 * prevents XSS token theft and CSRF. SSRF is prevented by a fixed internal
 * URL (FABRIC_API_URL env var, set by the operator in docker-compose) and a
 * strict allowlist check on the path segments.
 */
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
// SSRF guard: only allow connections to the operator-configured backend.
// Never derived from user input.
const API_BASE = (() => {
  const raw = (process.env.FABRIC_API_URL ?? "http://localhost:8000").trim();
  try {
    const u = new URL(raw);
    if (!["http:", "https:"].includes(u.protocol)) {
      throw new Error("unsupported protocol");
    }
    return raw.replace(/\/$/, "");
  } catch {
    throw new Error(`Invalid FABRIC_API_URL: ${raw}`);
  }
})();

// Only allow path segments that are alphanumeric, hyphens, underscores,
// forward slashes, and periods (node IDs like "skills/fabric-ingest").
// This prevents path traversal and injection into the upstream URL.
const SAFE_PATH_RE = /^[a-zA-Z0-9/_.:-]+$/;

const ALLOWED_METHODS = new Set(["GET", "POST", "PUT", "DELETE"]);

async function proxy(
  request: NextRequest,
  props: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  const { method } = request;
  if (!ALLOWED_METHODS.has(method)) {
    return NextResponse.json({ error: "method_not_allowed" }, { status: 405 });
  }

  const token = (await cookies()).get("fab_token")?.value;
  if (!token) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const { path } = await props.params;
  const backendPath = path.join("/");

  // Reject paths with traversal sequences or unsafe characters.
  if (!SAFE_PATH_RE.test(backendPath) || backendPath.includes("..")) {
    return NextResponse.json({ error: "invalid_path" }, { status: 400 });
  }

  const search = request.nextUrl.search;
  const backendUrl = `${API_BASE}/api/v1/${backendPath}${search}`;

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };

  const init: RequestInit = { method, headers };
  if (method !== "GET" && method !== "DELETE") {
    const body = await request.text();
    if (body) init.body = body;
  } else if (method === "DELETE") {
    const body = await request.text();
    if (body) init.body = body;
  }

  try {
    const upstream = await fetch(backendUrl, init);
    const data = await upstream.json().catch(() => ({}));
    return NextResponse.json(data, { status: upstream.status });
  } catch {
    return NextResponse.json({ error: "upstream_unavailable" }, { status: 502 });
  }
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as DELETE };
