/**
 * Server-side auth gate.
 *
 * Runs on the Next.js edge before any page renders. Reads the httpOnly
 * `fab_token` cookie — if absent, redirects to /login before the
 * component tree ever mounts. This eliminates the "brief render before
 * redirect" issue that client-side-only checks suffer from.
 */
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PREFIXES = ["/login", "/api/auth"];

export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;

  // Always allow public paths and Next.js internals.
  const isPublic = PUBLIC_PREFIXES.some((p) => pathname.startsWith(p));
  if (isPublic) return NextResponse.next();

  const token = request.cookies.get("fab_token");
  if (!token?.value) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  // Skip static assets and Next.js internals.
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
