import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import getConfig from "next/config";

const { serverRuntimeConfig } = getConfig() as {
  serverRuntimeConfig: { fabricApiUrl: string };
};
const API_BASE = serverRuntimeConfig.fabricApiUrl ?? "http://localhost:8000";

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
  }).catch(() => null);

  if (!upstream) {
    return NextResponse.json({ error: "upstream_unavailable" }, { status: 502 });
  }

  if (!upstream.ok) {
    const data = await upstream.json().catch(() => ({}));
    return NextResponse.json(data, { status: upstream.status });
  }

  const { token, expires_at, token_type } = await upstream.json();

  // Set httpOnly cookie — inaccessible to browser JS (prevents XSS token theft).
  cookies().set("fab_token", token, {
    httpOnly: true,
    secure: true,
    sameSite: "strict",
    path: "/",
    maxAge: TOKEN_MAX_AGE,
  });

  // Return non-sensitive confirmation to the browser.
  return NextResponse.json({ expires_at, token_type }, { status: 200 });
}
