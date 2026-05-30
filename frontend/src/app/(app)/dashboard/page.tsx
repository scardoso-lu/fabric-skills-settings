"use client";

import { useStats } from "@/hooks/useNodes";
import { kindBadgeClass } from "@/lib/utils";

export default function DashboardPage() {
  const { data, error, isLoading } = useStats();

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

      {isLoading && (
        <div className="flex justify-center py-12">
          <span className="loading loading-spinner loading-lg" />
        </div>
      )}

      {error && (
        <div role="alert" className="alert alert-error">
          <span>Failed to load stats: {error.message}</span>
        </div>
      )}

      {data && (
        <div className="flex flex-col gap-6">
          {/* Summary stats */}
          <div className="stats stats-horizontal shadow bg-base-200 w-full">
            <div className="stat">
              <div className="stat-title">Total Nodes</div>
              <div className="stat-value">{data.nodes}</div>
            </div>
            <div className="stat">
              <div className="stat-title">Total Edges</div>
              <div className="stat-value">{data.edges}</div>
            </div>
            <div className="stat">
              <div className="stat-title">Last Built</div>
              <div className="stat-desc text-sm">
                {data.built_at
                  ? new Date(data.built_at).toLocaleString()
                  : "—"}
              </div>
            </div>
          </div>

          {/* Kind breakdown */}
          <div className="card bg-base-200 shadow">
            <div className="card-body">
              <h2 className="card-title text-base">Nodes by kind</h2>
              <div className="flex flex-wrap gap-3">
                {Object.entries(data.by_kind)
                  .sort(([, a], [, b]) => b - a)
                  .map(([kind, count]) => (
                    <div key={kind} className="flex items-center gap-1.5">
                      <span className={`badge ${kindBadgeClass(kind)}`}>
                        {kind}
                      </span>
                      <span className="font-mono font-bold text-sm">{count}</span>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
