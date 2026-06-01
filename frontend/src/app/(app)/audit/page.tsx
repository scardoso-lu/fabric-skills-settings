"use client";

import { useState, useEffect, useCallback } from "react";
import { getAuditLog, clearAuditLog, exportAuditCsv } from "@/lib/audit";
import type { AuditEntry, AuditAction } from "@/lib/audit";

const ACTION_BADGE: Record<AuditAction, string> = {
  create: "badge-success",
  update: "badge-info",
  delete: "badge-error",
  edge_add: "badge-primary",
  edge_remove: "badge-warning",
  login: "badge-neutral",
};

const ALL_ACTIONS: AuditAction[] = ["login", "create", "update", "delete", "edge_add", "edge_remove"];

type DateFilter = "all" | "today" | "week";

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [actionFilter, setActionFilter] = useState<AuditAction | "">("");
  const [dateFilter, setDateFilter] = useState<DateFilter>("all");
  const [kindFilter, setKindFilter] = useState("");
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const load = useCallback(() => setEntries(getAuditLog()), []);

  useEffect(() => {
    load();
  }, [load]);

  const kinds = Array.from(new Set(entries.map((e) => e.nodeKind).filter(Boolean))) as string[];

  const filtered = entries.filter((e) => {
    if (actionFilter && e.action !== actionFilter) return false;
    if (kindFilter && e.nodeKind !== kindFilter) return false;
    if (dateFilter === "today") {
      const start = new Date();
      start.setHours(0, 0, 0, 0);
      if (e.ts < start.getTime()) return false;
    } else if (dateFilter === "week") {
      if (e.ts < Date.now() - 7 * 86_400_000) return false;
    }
    return true;
  });

  function handleClear() {
    clearAuditLog();
    setEntries([]);
    setShowClearConfirm(false);
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-slate-900">Audit Log</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Complete record of all create, update, and delete operations
        </p>
      </div>

      {/* Toolbar */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex flex-wrap items-center gap-3">
          {/* Action filter */}
          <select
            className="select select-bordered select-sm"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value as AuditAction | "")}
          >
            <option value="">All actions</option>
            {ALL_ACTIONS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>

          {/* Kind filter */}
          {kinds.length > 0 && (
            <select
              className="select select-bordered select-sm"
              value={kindFilter}
              onChange={(e) => setKindFilter(e.target.value)}
            >
              <option value="">All kinds</option>
              {kinds.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          )}

          {/* Date filter */}
          <div className="flex gap-1">
            {(["all", "today", "week"] as DateFilter[]).map((f) => (
              <button
                key={f}
                type="button"
                className={`btn btn-xs ${dateFilter === f ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setDateFilter(f)}
              >
                {f === "all" ? "All time" : f === "today" ? "Today" : "This week"}
              </button>
            ))}
          </div>

          <div className="ml-auto flex items-center gap-2">
            <span className="text-xs text-slate-400">
              {filtered.length} / {entries.length} entries
            </span>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => exportAuditCsv(filtered)}
              disabled={filtered.length === 0}
            >
              <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
              </svg>
              Export CSV
            </button>
            <button
              type="button"
              className="btn btn-error btn-outline btn-sm"
              onClick={() => setShowClearConfirm(true)}
              disabled={entries.length === 0}
            >
              Clear log
            </button>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {filtered.length === 0 ? (
          <div className="text-center py-16">
            <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3">
              <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <p className="text-sm font-medium text-slate-500">No audit entries found</p>
            <p className="text-xs text-slate-400 mt-1">
              {entries.length > 0
                ? "Try adjusting the filters above"
                : "Operations you perform will be recorded here"}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="table table-sm w-full">
              <thead>
                <tr className="bg-slate-50" style={{ borderBottom: "1px solid #e2e8f0" }}>
                  <th className="text-xs font-semibold text-slate-500 uppercase tracking-wide py-3">
                    Timestamp
                  </th>
                  <th className="text-xs font-semibold text-slate-500 uppercase tracking-wide py-3">
                    Action
                  </th>
                  <th className="text-xs font-semibold text-slate-500 uppercase tracking-wide py-3">
                    Resource
                  </th>
                  <th className="text-xs font-semibold text-slate-500 uppercase tracking-wide py-3">
                    Kind
                  </th>
                  <th className="text-xs font-semibold text-slate-500 uppercase tracking-wide py-3">
                    Detail / Location
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((entry) => (
                  <tr
                    key={entry.id}
                    className="hover:bg-slate-50 transition-colors"
                    style={{ borderBottom: "1px solid #f1f5f9" }}
                  >
                    <td className="text-xs text-slate-500 font-mono whitespace-nowrap py-2.5">
                      {new Date(entry.ts).toLocaleString()}
                    </td>
                    <td className="py-2.5">
                      <span
                        className={`badge badge-xs ${ACTION_BADGE[entry.action] ?? "badge-ghost"}`}
                      >
                        {entry.action}
                      </span>
                    </td>
                    <td className="text-xs font-mono text-slate-700 py-2.5">
                      {entry.nodeId}
                    </td>
                    <td className="py-2.5">
                      {entry.nodeKind ? (
                        <span className="badge badge-xs badge-ghost">{entry.nodeKind}</span>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                    <td className="text-xs text-slate-500 py-2.5 max-w-xs">
                      {entry.detail ? (
                        <span className="truncate block" title={entry.detail}>
                          {entry.detail}
                        </span>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Clear confirm modal */}
      {showClearConfirm && (
        <dialog className="modal modal-open">
          <div className="modal-box">
            <h3 className="font-bold text-lg">Clear audit log?</h3>
            <p className="py-4 text-sm text-slate-600">
              This will permanently delete all{" "}
              <span className="font-semibold">{entries.length}</span> audit log entries. This
              action cannot be undone.
            </p>
            <div className="modal-action">
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setShowClearConfirm(false)}
              >
                Cancel
              </button>
              <button type="button" className="btn btn-error btn-sm" onClick={handleClear}>
                Clear all
              </button>
            </div>
          </div>
          <div className="modal-backdrop" onClick={() => setShowClearConfirm(false)} />
        </dialog>
      )}
    </div>
  );
}
