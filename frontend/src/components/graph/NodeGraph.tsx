"use client";

import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  type NodeTypes,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { GraphNode } from "@/lib/types";

const KIND_COLOR: Record<string, string> = {
  skill: "#8b5cf6",
  rule: "#f59e0b",
  content: "#3b82f6",
  memory: "#ec4899",
  "skill-fix": "#10b981",
  entry: "#ef4444",
  capability: "#6b7280",
  profile: "#6b7280",
};

function kindColor(kind: string): string {
  return KIND_COLOR[kind] ?? "#6b7280";
}

function shortLabel(id: string, max = 14): string {
  const seg = id.includes("/") ? id.split("/").pop()! : id;
  return seg.length > max ? seg.slice(0, max - 1) + "…" : seg;
}

interface CenterData extends Record<string, unknown> {
  label: string;
  kind: string;
}

interface PeerData extends Record<string, unknown> {
  label: string;
  dir: "out" | "in";
  onSelect: () => void;
}

function CenterNodeComp({ data }: { data: CenterData }) {
  const color = kindColor(data.kind);
  return (
    <div
      style={{
        width: 72,
        height: 72,
        borderRadius: "50%",
        background: color,
        opacity: 0.9,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        color: "#fff",
        fontWeight: 700,
        fontSize: 11,
        textAlign: "center",
        padding: 4,
        boxSizing: "border-box",
      }}
    >
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <span style={{ lineHeight: 1.2 }}>{data.label}</span>
      <span style={{ fontSize: 9, fontWeight: 400, opacity: 0.8, marginTop: 2 }}>
        {data.kind}
      </span>
    </div>
  );
}

function PeerNodeComp({ data }: { data: PeerData }) {
  const color = data.dir === "out" ? "#818cf8" : "#fb923c";
  return (
    <div
      onClick={data.onSelect}
      style={{
        width: 48,
        height: 48,
        borderRadius: "50%",
        background: "#1f2937",
        border: `2px solid ${color}`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: "#9ca3af",
        fontSize: 9,
        textAlign: "center",
        padding: 4,
        boxSizing: "border-box",
        cursor: "pointer",
      }}
    >
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      {data.label}
    </div>
  );
}

const NODE_TYPES: NodeTypes = {
  center: CenterNodeComp as unknown as NodeTypes[string],
  peer: PeerNodeComp as unknown as NodeTypes[string],
};

const MAX_EACH = 8;
const ORBIT_R = 160;

function buildGraph(
  node: GraphNode,
  onSelectNode: (id: string) => void,
): { nodes: Node[]; edges: Edge[] } {
  const allOut = node.links ?? [];
  const allIn = (node.inbound_links ?? []).filter((id) => !allOut.includes(id));
  const outIds = allOut.slice(0, MAX_EACH);
  const inIds = allIn.slice(0, MAX_EACH);

  const nodes: Node[] = [];
  const edges: Edge[] = [];

  nodes.push({
    id: "__center__",
    type: "center",
    position: { x: 0, y: 0 },
    data: { label: shortLabel(node.title || node.id, 12), kind: node.kind },
    draggable: false,
  });

  function placeArc(
    ids: string[],
    dir: "out" | "in",
    startDeg: number,
    endDeg: number,
  ) {
    ids.forEach((id, i) => {
      const t = ids.length === 1 ? 0.5 : i / (ids.length - 1);
      const angleDeg = startDeg + t * (endDeg - startDeg);
      const angleRad = (angleDeg * Math.PI) / 180;
      const x = ORBIT_R * Math.cos(angleRad);
      const y = ORBIT_R * Math.sin(angleRad);

      nodes.push({
        id,
        type: "peer",
        position: { x, y },
        data: { label: shortLabel(id), dir, onSelect: () => onSelectNode(id) },
      });

      if (dir === "out") {
        edges.push({
          id: `e-out-${id}`,
          source: "__center__",
          target: id,
          style: { stroke: "#818cf8", strokeOpacity: 0.6 },
          markerEnd: { type: "arrowclosed" as const, color: "#818cf8" },
        });
      } else {
        edges.push({
          id: `e-in-${id}`,
          source: id,
          target: "__center__",
          style: { stroke: "#fb923c", strokeOpacity: 0.6 },
          markerEnd: { type: "arrowclosed" as const, color: "#fb923c" },
        });
      }
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

  return { nodes, edges };
}

interface NodeGraphProps {
  node: GraphNode;
  onSelectNode: (id: string) => void;
}

export function NodeGraph({ node, onSelectNode }: NodeGraphProps) {
  const { nodes: initNodes, edges: initEdges } = useMemo(
    () => buildGraph(node, onSelectNode),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [node.id],
  );

  const [nodes, , onNodesChange] = useNodesState(initNodes);
  const [edges, , onEdgesChange] = useEdgesState(initEdges);

  const allOut = node.links ?? [];
  const allIn = (node.inbound_links ?? []).filter((id) => !allOut.includes(id));
  const truncated = allOut.length > MAX_EACH || allIn.length > MAX_EACH;

  return (
    <div style={{ height: 320, position: "relative" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={NODE_TYPES}
        nodeOrigin={[0.5, 0.5]}
        fitView
        colorMode="dark"
        nodesConnectable={false}
        connectOnClick={false}
        elementsSelectable={false}
        panOnScroll
        zoomOnScroll={false}
      >
        <Background color="#374151" gap={20} />
        <Controls showInteractive={false} />
      </ReactFlow>
      {truncated && (
        <div
          style={{
            position: "absolute",
            bottom: 6,
            left: 0,
            right: 0,
            textAlign: "center",
            fontSize: 10,
            color: "#6b7280",
            pointerEvents: "none",
          }}
        >
          showing first {MAX_EACH} of each — click a neighbor to explore
        </div>
      )}
    </div>
  );
}
