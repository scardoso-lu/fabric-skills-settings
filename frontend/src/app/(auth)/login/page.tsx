"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { z } from "zod";
import { login } from "@/lib/api";
import { isAuthenticated, setExpiresAt } from "@/lib/auth";
import { logAudit } from "@/lib/audit";

const loginSchema = z.object({
  apiKey: z.string().min(8, "API key must be at least 8 characters"),
});

export default function LoginPage() {
  const router = useRouter();
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated()) router.replace("/dashboard");
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const result = loginSchema.safeParse({ apiKey });
    if (!result.success) {
      setError(result.error.errors[0]?.message ?? "Invalid input");
      return;
    }
    setLoading(true);
    try {
      const { expires_at, ip, userAgent } = await login(apiKey);
      setExpiresAt(expires_at);
      logAudit({
        ts: Date.now(),
        action: "login",
        nodeId: "auth/login",
        nodeKind: "auth",
        detail: [ip && `from ${ip}`, userAgent].filter(Boolean).join(" · ") || undefined,
      });
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4"
      style={{ background: "#f8fafc" }}
    >
      <div className="w-full max-w-sm">
        {/* Brand mark */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center shadow-sm"
            style={{ background: "#2563eb" }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
          </div>
          <div>
            <p className="text-lg font-bold text-slate-900 leading-tight">Fabric Platform</p>
            <p className="text-xs text-slate-400 leading-tight">Admin Console</p>
          </div>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8">
          <h2 className="text-lg font-semibold text-slate-900 mb-1">Sign in</h2>
          <p className="text-sm text-slate-500 mb-6">
            Enter your API key to access the console
          </p>

          {error && (
            <div role="alert" className="alert alert-error text-sm py-2.5 mb-4">
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
                <circle cx="12" cy="12" r="10" />
                <line x1="15" y1="9" x2="9" y2="15" />
                <line x1="9" y1="9" x2="15" y2="15" />
              </svg>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <label className="form-control w-full">
              <div className="label pb-1">
                <span className="label-text text-sm font-medium text-slate-700">API Key</span>
              </div>
              <input
                type="password"
                className="input input-bordered w-full"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="••••••••••••••••"
                autoComplete="current-password"
                autoFocus
              />
            </label>
            <button
              type="submit"
              className="btn btn-primary w-full mt-1"
              disabled={loading}
            >
              {loading ? (
                <span className="loading loading-spinner loading-sm" />
              ) : null}
              Sign in
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-slate-400 mt-6">
          Access is restricted to authorized personnel
        </p>
      </div>
    </div>
  );
}
