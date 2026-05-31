/**
 * Edge middleware: auth gate + per-request CSP nonce.
 *
 * Generates a fresh nonce on every request and writes it to:
 *   - `x-nonce` request header  → Next.js reads this and injects it into its
 *     own inline bootstrap scripts automatically (built-in nonce support).
 *   - `Content-Security-Policy` request header  → same, for framework use.
 *   - `Content-Security-Policy` response header → enforced by the browser.
 *
 * The static security headers (X-Frame-Options etc.) stay in next.config.mjs.
 * Only CSP lives here because it must be dynamic (per-request nonce).
 */
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PREFIXES = ["/login", "/api/auth"];

function buildCsp(nonce: string): string {
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}'`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");
}

export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;

  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const csp = buildCsp(nonce);

  const isPublic = PUBLIC_PREFIXES.some((p) => pathname.startsWith(p));
  if (!isPublic) {
    const token = request.cookies.get("fab_token");
    if (!token?.value) {
      // API routes return 401 JSON; page routes redirect to /login.
      if (pathname.startsWith("/api/")) {
        return NextResponse.json({ error: "unauthorized" }, { status: 401 });
      }
      return NextResponse.redirect(new URL("/login", request.url));
    }
  }

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);

  const response = NextResponse.next({
    request: { headers: requestHeaders },
  });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
