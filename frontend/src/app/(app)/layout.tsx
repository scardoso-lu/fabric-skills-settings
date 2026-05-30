"use client";

/**
 * App shell layout.
 *
 * Auth protection is enforced server-side by middleware.ts before this
 * component renders. The token refresh hook keeps the session alive
 * by proactively refreshing 10 minutes before expiry.
 */
import { Sidebar } from "@/components/layout/Sidebar";
import { useTokenRefresh } from "@/hooks/useTokenRefresh";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  useTokenRefresh();
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto p-6">{children}</main>
    </div>
  );
}
