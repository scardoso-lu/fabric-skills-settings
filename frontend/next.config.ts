import type { NextConfig } from "next";

const FABRIC_API_URL = process.env.FABRIC_API_URL ?? "http://localhost:8000";

const securityHeaders = [
  { key: "X-DNS-Prefetch-Control", value: "on" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "script-src 'self'",          // no inline scripts
      "style-src 'self' 'unsafe-inline'", // Tailwind requires inline styles
      "img-src 'self' data:",
      "font-src 'self'",
      "connect-src 'self'",          // all API calls go through /api/proxy (same origin)
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join("; "),
  },
];

const nextConfig: NextConfig = {
  output: "standalone",

  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },

  // Expose the internal API URL to server-side API routes only (not client).
  serverRuntimeConfig: {
    fabricApiUrl: FABRIC_API_URL,
  },
};

export default nextConfig;
