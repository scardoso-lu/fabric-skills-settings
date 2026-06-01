"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useStats } from "@/hooks/useNodes";
import { kindBadgeClass } from "@/lib/utils";
import { getAuditLog } from "@/lib/audit";
import type { AuditEntry, AuditAction } from "@/lib/audit";

const ACTION_BADGE: Record<AuditAction, string> = {
  create: "badge-success",
  update: "badge-info",
  delete: "badge-error",
  edge_add: "badge-primary",
  edge_remove: "badge-warning",
  login: "badge-neutral",
};

function timeAgo(ts: number): string {
  const diff = Date.now() - ts;
  if (diff < 60_000) return "just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

export default function DashboardPage() {
  const { data, error, isLoading } = useStats();
  const [recentActivity, setRecentActivity] = useState<AuditEntry[]>([]);

  useEffect(() => {
    setRecentActivity(getAuditLog().slice(0, 8));
  }, []);

  const maxKindCount = data ? Math.max(...Object.values(data.by_kind), 1) : 1;

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-slate-900">Overview</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Graph health, node inventory, and recent activity
        </p>
      </div>

      {isLoading && (
        <div className="flex justify-center py-16">
          <span className="loading loading-spinner loading-md text-primary" />
        </div>
      )}

      {error && (
        <div role="alert" className="alert alert-error mb-4">
          <span>Failed to load stats: {error.message}</span>
        </div>
      )}

      {data && (
        <div className="flex flex-col gap-5">
          {/* KPI row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              {
                label: "Total Nodes",
                value: data.nodes,
                sub: "in knowledge graph",
                color: "text-blue-600",
                icon: (
                  <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="3" />
                    <path d="M12 2v4M12 18v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M2 12h4M18 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83" />
                  </svg>
                ),
              },
              {
                label: "Total Edges",
                value: data.edges,
                sub: "graph connections",
                color: "text-violet-600",
                icon: (
                  <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71" />
                    <path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71" />
                  </svg>
                ),
              },
              {
                label: "Skills",
                value: data.by_kind["skill"] ?? 0,
                sub: "agent skill profiles",
                color: "text-indigo-600",
                icon: (
                  <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="#4f46e5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                ),
              },
              {
                label: "Rules",
                value: data.by_kind["rule"] ?? 0,
                sub: "governance rules",
                color: "text-amber-600",
                icon: (
                  <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="#d97706" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  </svg>
                ),
              },
            ].map((kpi) => (
              <div
                key={kpi.label}
                className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm"
              >
                <div className="flex items-start justify-between">
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                    {kpi.label}
                  </p>
                  <span className="opacity-60">{kpi.icon}</span>
                </div>
                <p className={`text-3xl font-bold mt-2 ${kpi.color}`}>{kpi.value}</p>
                <p className="text-xs text-slate-400 mt-0.5">{kpi.sub}</p>
              </div>
            ))}
          </div>

          <div className="grid md:grid-cols-2 gap-5">
            {/* Node distribution */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-slate-700">Node Distribution</h2>
                <span className="text-xs text-slate-400">by kind</span>
              </div>
              <div className="flex flex-col gap-3">
                {Object.entries(data.by_kind)
                  .sort(([, a], [, b]) => b - a)
                  .map(([kind, count]) => (
                    <div key={kind}>
                      <div className="flex items-center justify-between mb-1">
                        <span className={`badge badge-xs ${kindBadgeClass(kind)}`}>
                          {kind}
                        </span>
                        <span className="text-xs font-mono font-semibold text-slate-600">
                          {count}
                        </span>
                      </div>
                      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full bg-primary opacity-70 transition-all duration-500"
                          style={{ width: `${(count / maxKindCount) * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
              </div>
            </div>

            <div className="flex flex-col gap-5">
              {/* Graph status */}
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-semibold text-slate-700">Graph Status</h2>
                  <Link href="/health" className="text-xs text-primary hover:underline">
                    Details
                  </Link>
                </div>
                <div className="flex items-center gap-2.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-success" />
                  <span className="text-sm font-medium text-slate-700">
                    Operational — graph is built and serving
                  </span>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3">
                  <div className="bg-slate-50 rounded-lg px-3 py-2">
                    <p className="text-xs text-slate-400">Nodes</p>
                    <p className="text-lg font-bold text-slate-700">{data.nodes}</p>
                  </div>
                  <div className="bg-slate-50 rounded-lg px-3 py-2">
                    <p className="text-xs text-slate-400">Last built</p>
                    <p className="text-xs font-medium text-slate-600 mt-0.5">
                      {data.built_at
                        ? new Date(data.built_at).toLocaleString(undefined, {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "—"}
                    </p>
                  </div>
                </div>
              </div>

              {/* Recent activity */}
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 flex-1">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-semibold text-slate-700">Recent Activity</h2>
                  <Link href="/audit" className="text-xs text-primary hover:underline">
                    View all
                  </Link>
                </div>
                {recentActivity.length === 0 ? (
                  <div className="text-center py-4">
                    <p className="text-xs text-slate-400 italic">
                      No activity recorded yet. Create, update, or delete nodes to see entries here.
                    </p>
                  </div>
                ) : (
                  <div className="flex flex-col gap-2.5">
                    {recentActivity.map((entry) => (
                      <div
                        key={entry.id}
                        className="flex items-center justify-between gap-2"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <span
                            className={`badge badge-xs shrink-0 ${ACTION_BADGE[entry.action] ?? "badge-ghost"}`}
                          >
                            {entry.action}
                          </span>
                          <span className="text-xs text-slate-600 truncate font-mono">
                            {entry.nodeId}
                          </span>
                        </div>
                        <span className="text-xs text-slate-400 shrink-0">
                          {timeAgo(entry.ts)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
