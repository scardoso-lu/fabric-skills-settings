"use client";

/**
 * Client-side auth helpers.
 *
 * The JWT is stored in an httpOnly, SameSite=Strict cookie set by the
 * /api/auth/login server route. Browser JS cannot read it (no sessionStorage).
 * The expiry hint is stored in a non-sensitive, non-httpOnly cookie so
 * the client can decide whether to refresh without a round-trip.
 */

const EXPIRY_KEY = "fab_expires_at";

export function getExpiresAt(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)fab_expires_at=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export function setExpiresAt(expiresAt: string): void {
  if (typeof document === "undefined") return;
  const maxAge = 3600;
  document.cookie = `${EXPIRY_KEY}=${encodeURIComponent(expiresAt)}; path=/; max-age=${maxAge}; SameSite=Strict`;
}

export function clearExpiresAt(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${EXPIRY_KEY}=; path=/; max-age=0; SameSite=Strict`;
}

export function isTokenExpired(): boolean {
  const expiry = getExpiresAt();
  if (!expiry) return true;
  return new Date(expiry) <= new Date(Date.now() + 60_000); // 1-min buffer
}

export function isAuthenticated(): boolean {
  return !isTokenExpired();
}

export async function logout(): Promise<void> {
  clearExpiresAt();
  await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
}
