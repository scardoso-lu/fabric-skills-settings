export type AuditAction = "create" | "update" | "delete" | "edge_add" | "edge_remove";

export interface AuditEntry {
  id: string;
  ts: number;
  action: AuditAction;
  nodeId: string;
  nodeKind?: string;
  detail?: string;
}

const KEY = "fab_audit_log";
const MAX = 500;

export function logAudit(entry: Omit<AuditEntry, "id">): void {
  if (typeof window === "undefined") return;
  const next: AuditEntry = { ...entry, id: crypto.randomUUID() };

  // Persist to localStorage for the in-app /audit view.
  try {
    const updated = [next, ...getAuditLog()].slice(0, MAX);
    localStorage.setItem(KEY, JSON.stringify(updated));
  } catch {
    // ignore quota errors
  }

  // Forward to the server so journald captures it via Next.js stdout.
  fetch("/api/audit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(next),
  }).catch(() => {
    // best-effort — never interrupt the caller
  });
}

export function getAuditLog(): AuditEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as AuditEntry[]) : [];
  } catch {
    return [];
  }
}

export function clearAuditLog(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(KEY);
}

export function exportAuditCsv(entries: AuditEntry[]): void {
  const header = "timestamp,action,nodeId,kind,detail";
  const rows = entries.map((e) =>
    [
      new Date(e.ts).toISOString(),
      e.action,
      `"${e.nodeId}"`,
      e.nodeKind ?? "",
      `"${(e.detail ?? "").replace(/"/g, '""')}"`,
    ].join(","),
  );
  const csv = [header, ...rows].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `fabric-audit-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
