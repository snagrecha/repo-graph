import { useRef, useEffect, useMemo, useState } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import type { GraphNode, GraphLink, NodeType, OverlayMode } from '../types';

const NODE_COLORS: Record<NodeType, string> = {
  file: '#64748b',
  class: '#3b82f6',
  function: '#22c55e',
  module: '#a855f7',
  symbol: '#f59e0b',
};

const EDGE_COLORS: Record<string, string> = {
  imports: '#6366f1',
  calls: '#22c55e',
  inherits: '#f59e0b',
  contains: '#475569',
  co_changes_with: '#ec4899',
};

// Lerp between two hex colors by t (0..1)
function lerpHex(a: string, b: string, t: number): string {
  const parse = (hex: string) => {
    const c = hex.replace('#', '');
    return [
      parseInt(c.slice(0, 2), 16),
      parseInt(c.slice(2, 4), 16),
      parseInt(c.slice(4, 6), 16),
    ] as [number, number, number];
  };
  const [ar, ag, ab] = parse(a);
  const [br, bg, bb] = parse(b);
  const r = Math.round(ar + (br - ar) * t);
  const g = Math.round(ag + (bg - ag) * t);
  const bl = Math.round(ab + (bb - ab) * t);
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${bl.toString(16).padStart(2, '0')}`;
}

function heatColor(value: unknown, min: number, max: number): string {
  const v = typeof value === 'number' ? value : 0;
  const t = max === min ? 0 : (v - min) / (max - min);
  // cool blue -> warm red
  return lerpHex('#1d4ed8', '#dc2626', Math.max(0, Math.min(1, t)));
}

interface Props {
  nodes: GraphNode[];
  links: GraphLink[];
  selectedNodeId: string | null;
  blastRadiusSet: { upstream: Set<string>; downstream: Set<string> } | null;
  overlayMode: OverlayMode;
  overlayData: Record<string, unknown> | null;
  searchQuery: string;
  loading: boolean;
  onNodeClick: (node: GraphNode) => void;
}

export function GraphCanvas({
  nodes,
  links,
  selectedNodeId,
  blastRadiusSet,
  overlayMode,
  overlayData,
  searchQuery,
  loading,
  onNodeClick,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        setDimensions({ width, height });
      }
    });
    ro.observe(el);
    // Initial size
    setDimensions({ width: el.clientWidth, height: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  const graphData = useMemo(
    () => ({ nodes: nodes as GraphNode[], links }),
    [nodes, links],
  );

  // Precompute overlay min/max for heat mapping
  const { overlayMin, overlayMax } = useMemo(() => {
    if (!overlayData || overlayMode === 'none') return { overlayMin: 0, overlayMax: 1 };
    const values = Object.values(overlayData)
      .filter((v): v is number => typeof v === 'number');
    if (values.length === 0) return { overlayMin: 0, overlayMax: 1 };
    return { overlayMin: Math.min(...values), overlayMax: Math.max(...values) };
  }, [overlayData, overlayMode]);

  const hasBlast = blastRadiusSet !== null;
  const hasSearch = searchQuery.trim().length > 0;
  const searchLower = searchQuery.toLowerCase();

  function nodeColor(node: GraphNode): string {
    // Blast radius coloring takes highest precedence
    if (hasBlast) {
      if (node.id === selectedNodeId) return '#f8fafc';
      if (blastRadiusSet!.upstream.has(node.id)) return '#f97316'; // orange = upstream
      if (blastRadiusSet!.downstream.has(node.id)) return '#06b6d4'; // cyan = downstream
      return '#1e293b'; // dim non-radius nodes
    }

    // Search filter: highlight matches, dim non-matches
    if (hasSearch) {
      const matches =
        node.name.toLowerCase().includes(searchLower) ||
        node.file_path.toLowerCase().includes(searchLower);
      if (!matches) return '#1e293b';
    }

    // Overlay heat map
    if (overlayMode !== 'none' && overlayData) {
      const val = overlayData[node.id];
      if (val !== undefined) {
        return heatColor(val, overlayMin, overlayMax);
      }
    }

    // Selected node
    if (node.id === selectedNodeId) return '#f8fafc';

    // Default: by type
    return NODE_COLORS[node.type] ?? '#64748b';
  }

  function nodeVal(node: GraphNode): number {
    return Math.max(1, (node.degree ?? 0) / 2 + 1);
  }

  function linkColor(link: GraphLink): string {
    if (hasBlast || hasSearch) return '#1e293b';
    return EDGE_COLORS[link.type] ?? '#334155';
  }

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%', position: 'relative' }}>
      {loading && (
        <div className="graph-loading">
          <div className="spinner" />
        </div>
      )}
      {!loading && nodes.length === 0 && (
        <div className="graph-empty">
          <p>No graph data available.</p>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Run <code>codenexus start .</code> to index your repository.
          </p>
        </div>
      )}
      {nodes.length > 0 && (
        <ForceGraph3D
          width={dimensions.width}
          height={dimensions.height}
          graphData={graphData}
          backgroundColor="#0a0f1e"
          nodeLabel={(node) => {
            const n = node as GraphNode;
            return `${n.name} (${n.type})`;
          }}
          nodeColor={(node) => nodeColor(node as GraphNode)}
          nodeVal={(node) => nodeVal(node as GraphNode)}
          linkColor={(link) => linkColor(link as GraphLink)}
          onNodeClick={(node) => onNodeClick(node as GraphNode)}
          showNavInfo={false}
          enableNodeDrag={true}
        />
      )}
    </div>
  );
}
