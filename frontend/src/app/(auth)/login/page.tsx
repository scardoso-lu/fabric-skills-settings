"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { z } from "zod";
import { login } from "@/lib/api";
import { isAuthenticated, setExpiresAt } from "@/lib/auth";

const loginSchema = z.object({
  apiKey: z.string().min(8, "API key must be at least 8 characters"),
});

export default function LoginPage() {
  const router = useRouter();
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Middleware already blocks unauthenticated access to app routes,
    // but redirect authenticated users who land here directly.
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
      const { expires_at } = await login(apiKey);
      // Store only the expiry hint client-side (not the token itself).
      setExpiresAt(expires_at);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-base-100 p-4">
      <div className="card w-full max-w-sm bg-base-200 shadow-xl">
        <div className="card-body gap-4">
          <h2 className="card-title text-xl">fabric admin</h2>
          <p className="text-sm text-base-content/60">
            Enter your API key to access the server manager
          </p>

          {error && (
            <div role="alert" className="alert alert-error text-sm py-2">
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <label className="form-control w-full">
              <div className="label">
                <span className="label-text">API Key</span>
              </div>
              <input
                type="password"
                className="input input-bordered w-full"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="your-api-key"
                autoComplete="current-password"
                autoFocus
              />
            </label>
            <button
              type="submit"
              className="btn btn-primary w-full"
              disabled={loading}
            >
              {loading ? (
                <span className="loading loading-spinner loading-sm" />
              ) : null}
              Sign in
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
