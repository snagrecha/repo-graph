export type NodeType = 'file' | 'class' | 'function' | 'module' | 'symbol';
export type EdgeType = 'imports' | 'calls' | 'inherits' | 'contains' | 'co_changes_with';
export type OverlayMode = 'none' | 'complexity' | 'churn' | 'ownership';

export interface ApiNode {
  id: string;
  type: NodeType;
  name: string;
  file_path: string;
  start_line: number | null;
  end_line: number | null;
  language: string | null;
  metadata: Record<string, unknown>;
}

export interface ApiEdge {
  source_id: string;
  target_id: string;
  type: EdgeType;
  metadata: Record<string, unknown>;
}

export interface GraphResponse {
  nodes: ApiNode[];
  edges: ApiEdge[];
  node_count: number;
  edge_count: number;
}

export interface NodeDetailResponse {
  node: ApiNode;
  incoming: ApiEdge[];
  outgoing: ApiEdge[];
}

export interface BlastRadiusResponse {
  node_id: string;
  upstream: ApiNode[];
  downstream: ApiNode[];
}

// Extended for react-force-graph-3d (library adds x/y/z/vx/vy/vz in place)
export interface GraphNode extends ApiNode {
  degree?: number;
  x?: number;
  y?: number;
  z?: number;
  vx?: number;
  vy?: number;
  vz?: number;
}

export interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  type: EdgeType;
  metadata: Record<string, unknown>;
}
