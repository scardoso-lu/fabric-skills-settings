"use client";

import type { GraphNode } from "@/lib/types";

const W = 560;
const H = 300;
const CX = W / 2;
const CY = H / 2;
const ORBIT_R = 145;
const CENTER_R = 30;
const PEER_R = 20;
const MAX_EACH = 8;

const KIND_FILL: Record<string, string> = {
  skill: "#8b5cf6",
  rule: "#f59e0b",
  content: "#3b82f6",
  memory: "#ec4899",
  "skill-fix": "#10b981",
  entry: "#ef4444",
  capability: "#6b7280",
  profile: "#6b7280",
};

function kindFill(kind: string): string {
  return KIND_FILL[kind] ?? "#6b7280";
}

function shortLabel(id: string, max = 13): string {
  const seg = id.includes("/") ? id.split("/").pop()! : id;
  return seg.length > max ? seg.slice(0, max - 1) + "…" : seg;
}

interface Peer {
  id: string;
  dir: "out" | "in";
  x: number;
  y: number;
  angle: number;
}

function computePeers(outIds: string[], inIds: string[]): Peer[] {
  const peers: Peer[] = [];

  function placeArc(ids: string[], dir: "out" | "in", startDeg: number, endDeg: number) {
    if (ids.length === 0) return;
    const startR = (startDeg * Math.PI) / 180;
    const endR = (endDeg * Math.PI) / 180;
    ids.forEach((id, i) => {
      const t = ids.length === 1 ? 0.5 : i / (ids.length - 1);
      const angle = startR + t * (endR - startR);
      peers.push({
        id,
        dir,
        x: CX + ORBIT_R * Math.cos(angle),
        y: CY + ORBIT_R * Math.sin(angle),
        angle,
      });
    });
  }

  if (outIds.length > 0 && inIds.length > 0) {
    placeArc(outIds, "out", -80, 80);
    placeArc(inIds, "in", 100, 260);
  } else if (outIds.length > 0) {
    placeArc(outIds, "out", -120, 120);
  } else {
    placeArc(inIds, "in", -120, 120);
  }

  return peers;
}

function edgePts(
  x1: number, y1: number, r1: number,
  x2: number, y2: number, r2: number,
) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  return {
    x1: x1 + ux * (r1 + 2),
    y1: y1 + uy * (r1 + 2),
    x2: x2 - ux * (r2 + 10),
    y2: y2 - uy * (r2 + 10),
  };
}

interface NodeGraphProps {
  node: GraphNode;
  onSelectNode: (id: string) => void;
}

export function NodeGraph({ node, onSelectNode }: NodeGraphProps) {
  const allOut = node.links ?? [];
  const allIn = (node.inbound_links ?? []).filter((id) => !allOut.includes(id));
  const outIds = allOut.slice(0, MAX_EACH);
  const inIds = allIn.slice(0, MAX_EACH);
  const peers = computePeers(outIds, inIds);
  const truncated = allOut.length > MAX_EACH || allIn.length > MAX_EACH;
  const hasOut = outIds.length > 0;
  const hasIn = inIds.length > 0;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full select-none"
      style={{ maxHeight: 300 }}
      aria-label={`Neighborhood graph for ${node.id}`}
    >
      <defs>
        <marker id="arr-out" markerWidth="7" markerHeight="7" refX="5" refY="3.5" orient="auto">
          <path d="M0,0 L0,7 L7,3.5 z" fill="#818cf8" />
        </marker>
        <marker id="arr-in" markerWidth="7" markerHeight="7" refX="5" refY="3.5" orient="auto">
          <path d="M0,0 L0,7 L7,3.5 z" fill="#fb923c" />
        </marker>
      </defs>

      {/* Edges */}
      {peers.map((p) => {
        const isOut = p.dir === "out";
        const pts = isOut
          ? edgePts(CX, CY, CENTER_R, p.x, p.y, PEER_R)
          : edgePts(p.x, p.y, PEER_R, CX, CY, CENTER_R);
        return (
          <line
            key={`e-${p.id}`}
            x1={pts.x1} y1={pts.y1}
            x2={pts.x2} y2={pts.y2}
            stroke={isOut ? "#818cf8" : "#fb923c"}
            strokeWidth={1.5}
            strokeOpacity={0.5}
            markerEnd={`url(#arr-${isOut ? "out" : "in"})`}
          />
        );
      })}

      {/* Peer nodes */}
      {peers.map((p) => {
        const lx = p.x + Math.cos(p.angle) * (PEER_R + 12);
        const ly = p.y + Math.sin(p.angle) * (PEER_R + 12) + 3;
        const anchor =
          Math.cos(p.angle) > 0.4 ? "start"
          : Math.cos(p.angle) < -0.4 ? "end"
          : "middle";
        return (
          <g
            key={`n-${p.id}`}
            className="cursor-pointer"
            role="button"
            aria-label={p.id}
            onClick={() => onSelectNode(p.id)}
          >
            <circle
              cx={p.x} cy={p.y} r={PEER_R + 6}
              fill="transparent"
            />
            <circle
              cx={p.x} cy={p.y} r={PEER_R}
              fill="#1f2937"
              stroke={p.dir === "out" ? "#818cf8" : "#fb923c"}
              strokeWidth={1.5}
            />
            <text x={lx} y={ly} textAnchor={anchor} fontSize={9} fill="#9ca3af">
              {shortLabel(p.id)}
            </text>
          </g>
        );
      })}

      {/* Center node */}
      <circle cx={CX} cy={CY} r={CENTER_R} fill={kindFill(node.kind)} fillOpacity={0.85} />
      <text
        x={CX} y={CY + 1}
        textAnchor="middle" dominantBaseline="middle"
        fontSize={11} fontWeight={600} fill="white"
      >
        {shortLabel(node.title || node.id, 12)}
      </text>
      <text
        x={CX} y={CY + CENTER_R + 13}
        textAnchor="middle" fontSize={9} fill="#d1d5db"
      >
        {node.kind}
      </text>

      {/* Empty state */}
      {!hasOut && !hasIn && (
        <text
          x={CX} y={CY - CENTER_R - 16}
          textAnchor="middle" fontSize={11} fill="#6b7280"
        >
          No connections
        </text>
      )}

      {/* Legend */}
      {hasOut && (
        <g>
          <circle cx={14} cy={12} r={4} fill="#818cf8" />
          <text x={22} y={16} fontSize={9} fill="#9ca3af">
            {`→ outbound (${allOut.length})`}
          </text>
        </g>
      )}
      {hasIn && (
        <g>
          <circle cx={14} cy={hasOut ? 26 : 12} r={4} fill="#fb923c" />
          <text x={22} y={hasOut ? 30 : 16} fontSize={9} fill="#9ca3af">
            {`← inbound (${allIn.length})`}
          </text>
        </g>
      )}

      {truncated && (
        <text
          x={W / 2} y={H - 5}
          textAnchor="middle" fontSize={9} fill="#6b7280"
        >
          {`showing first ${MAX_EACH} of each — click a neighbor to explore`}
        </text>
      )}
    </svg>
  );
}
