/**
 * BFF proxy — forwards /api/proxy/** → backend /api/v1/**.
 *
 * All API calls from the browser go to this same-origin proxy. The proxy
 * reads the httpOnly `fab_token` cookie (inaccessible to browser JS) and
 * adds the Authorization header before forwarding to the FastMCP server.
 *
 * Security: token never touches browser JS; httpOnly + SameSite=Strict
 * prevents XSS token theft and CSRF.
 */
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import getConfig from "next/config";

const { serverRuntimeConfig } = getConfig() as {
  serverRuntimeConfig: { fabricApiUrl: string };
};
const API_BASE = serverRuntimeConfig.fabricApiUrl ?? "http://localhost:8000";

const ALLOWED_METHODS = new Set(["GET", "POST", "PUT", "DELETE"]);

async function proxy(
  request: NextRequest,
  { params }: { params: { path: string[] } },
): Promise<NextResponse> {
  const { method } = request;
  if (!ALLOWED_METHODS.has(method)) {
    return NextResponse.json({ error: "method_not_allowed" }, { status: 405 });
  }

  const token = cookies().get("fab_token")?.value;
  if (!token) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const backendPath = params.path.join("/");
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
