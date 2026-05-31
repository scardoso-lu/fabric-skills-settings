import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
const API_BASE = process.env.FABRIC_API_URL ?? "http://localhost:8000";
const IS_PROD = process.env.NODE_ENV === "production";
const TOKEN_MAX_AGE = 3600;

export async function POST(request: NextRequest): Promise<NextResponse> {
  const cookieStore = await cookies();
  const cookieToken = cookieStore.get("fab_token")?.value;

  // CLI clients pass the token as Authorization: Bearer instead of a cookie.
  const authHeader = request.headers.get("Authorization") ?? "";
  const bearerToken = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : "";

  const oldToken = cookieToken || bearerToken;
  if (!oldToken) {
    return NextResponse.json({ error: "no_session" }, { status: 401 });
  }

  const upstream = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { Authorization: `Bearer ${oldToken}` },
  }).catch((err: unknown) => {
    console.error("[auth/refresh] upstream fetch failed:", err);
    return null;
  });

  if (!upstream) {
    return NextResponse.json({ error: "upstream_unavailable" }, { status: 502 });
  }

  if (!upstream.ok) {
    console.warn("[auth/refresh] upstream returned", upstream.status);
    if (cookieToken) cookieStore.delete("fab_token");
    return NextResponse.json({ error: "refresh_failed" }, { status: upstream.status });
  }

  const { token, expires_at, token_type } = await upstream.json();

  // Update the httpOnly cookie for browser sessions.
  if (cookieToken) {
    cookieStore.set("fab_token", token, {
      httpOnly: true,
      secure: IS_PROD,
      sameSite: "strict",
      path: "/",
      maxAge: TOKEN_MAX_AGE,
    });
  }

  // Return the token in the body so CLI clients can read it directly.
  return NextResponse.json({ token, expires_at, token_type }, { status: 200 });
}
