import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import getConfig from "next/config";

const { serverRuntimeConfig } = getConfig() as {
  serverRuntimeConfig: { fabricApiUrl: string };
};
const API_BASE = serverRuntimeConfig.fabricApiUrl ?? "http://localhost:8000";
const IS_PROD = process.env.NODE_ENV === "production";
const TOKEN_MAX_AGE = 3600;

export async function POST(_request: NextRequest): Promise<NextResponse> {
  const oldToken = cookies().get("fab_token")?.value;
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
    cookies().delete("fab_token");
    return NextResponse.json({ error: "refresh_failed" }, { status: upstream.status });
  }

  const { token, expires_at, token_type } = await upstream.json();

  cookies().set("fab_token", token, {
    httpOnly: true,
    secure: IS_PROD,
    sameSite: "strict",
    path: "/",
    maxAge: TOKEN_MAX_AGE,
  });

  return NextResponse.json({ expires_at, token_type }, { status: 200 });
}
