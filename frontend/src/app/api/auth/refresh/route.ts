import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
const API_BASE = process.env.FABRIC_API_URL ?? "http://localhost:8000";
const IS_PROD = process.env.NODE_ENV === "production";
const TOKEN_MAX_AGE = 3600;

export async function POST(_request: NextRequest): Promise<NextResponse> {
  const cookieStore = await cookies();
  const oldToken = cookieStore.get("fab_token")?.value;
  if (!oldToken) {
    return NextResponse.json({ error: "no_session" }, { status: 401 });
  }

  const upstream = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { Authorization: `Bearer ${oldToken}` },
  }).catch(() => null);

  if (!upstream) {
    return NextResponse.json({ error: "upstream_unavailable" }, { status: 502 });
  }

  if (!upstream.ok) {
    cookieStore.delete("fab_token");
    return NextResponse.json({ error: "refresh_failed" }, { status: upstream.status });
  }

  const { token, expires_at, token_type } = await upstream.json();

  cookieStore.set("fab_token", token, {
    httpOnly: true,
    secure: IS_PROD,
    sameSite: "strict",
    path: "/",
    maxAge: TOKEN_MAX_AGE,
  });

  return NextResponse.json({ expires_at, token_type }, { status: 200 });
}
