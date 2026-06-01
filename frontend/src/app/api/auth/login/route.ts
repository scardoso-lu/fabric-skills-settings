import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
const API_BASE = process.env.FABRIC_API_URL ?? "http://localhost:8000";

// secure:true is set unconditionally. In local HTTP dev the browser will accept
// it from localhost (Chrome/Firefox both exempt localhost from the secure
// requirement). In production it enforces HTTPS.
const TOKEN_MAX_AGE = 3600; // 1 hour, matches JWT expiry

export async function POST(request: NextRequest): Promise<NextResponse> {
  let body: { api_key?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid_request" }, { status: 400 });
  }

  const apiKey = (body.api_key ?? "").trim();
  if (!apiKey) {
    return NextResponse.json({ error: "api_key_required" }, { status: 400 });
  }

  const upstream = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  }).catch((err: unknown) => {
    console.error("[auth/login] upstream fetch failed:", err);
    return null;
  });

  if (!upstream) {
    return NextResponse.json({ error: "upstream_unavailable" }, { status: 502 });
  }

  if (!upstream.ok) {
    const data = await upstream.json().catch(() => ({}));
    console.warn("[auth/login] upstream returned", upstream.status, data);
    return NextResponse.json(data, { status: upstream.status });
  }

  const { token, expires_at, token_type } = await upstream.json();

  const ip =
    request.headers.get("x-forwarded-for")?.split(",")[0].trim() ??
    request.headers.get("x-real-ip") ??
    "unknown";
  const userAgent = request.headers.get("user-agent") ?? "unknown";

  process.stdout.write(
    JSON.stringify({
      msg: "fabric-audit",
      ts: new Date().toISOString(),
      action: "login",
      nodeId: "auth/login",
      nodeKind: "auth",
      detail: `from ${ip}`,
      ip,
      userAgent,
    }) + "\n",
  );

  // Set httpOnly cookie — inaccessible to browser JS (prevents XSS token theft).
  (await cookies()).set("fab_token", token, {
    httpOnly: true,
    secure: true,
    sameSite: "strict",
    path: "/",
    maxAge: TOKEN_MAX_AGE,
  });

  // Return the token in the body so CLI clients can read it directly.
  // Browser clients use the httpOnly cookie above and ignore the token field.
  return NextResponse.json({ token, expires_at, token_type, ip, userAgent }, { status: 200 });
}
