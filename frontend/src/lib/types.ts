export type NodeKind =
  | "entry"
  | "content"
  | "skill"
  | "rule"
  | "memory"
  | "skill-fix"
  | "capability"
  | "profile";

export interface GraphNode {
  id: string;
  title: string;
  description: string;
  kind: NodeKind;
  path: string;
  managed: boolean;
  links?: string[];
  inbound_links?: string[];
  frontmatter?: Record<string, unknown>;
  body?: string;
}

export interface GraphStats {
  nodes: number;
  edges: number;
  by_kind: Record<string, number>;
  built_at: string;
}

export interface SearchHit {
  id: string;
  title: string;
  score: number;
  why_matched: string;
}

export interface Template {
  name: string;
  description: string;
  allowed_tools: string;
}

export interface TemplateDetail extends Template {
  frontmatter: Record<string, unknown>;
  body: string;
}

export interface WriteResult {
  id: string;
  path: string;
  action: string;
  nodes: number;
  edges: number;
}

export interface ApiError {
  error: string;
}
